"""
server.py — AgentTrade v2 FastAPI server with EventBus-based SSE streaming.

Subscribes to the EventBus and translates agent events to Server-Sent Events
for the React frontend. Also serves the structured procurement API.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Ensure project root is on path
ROOT = pathlib.Path(__file__).parent.absolute()
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

app = FastAPI(title="AgentTrade v2 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health & root
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    # Serve frontend index.html if available, otherwise API status
    frontend_index = ROOT / "frontend" / "dist" / "index.html"
    if frontend_index.exists():
        from fastapi.responses import FileResponse
        return FileResponse(str(frontend_index), media_type="text/html")
    return {"status": "AgentTrade v2 API is active"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


# ---------------------------------------------------------------------------
# Structured procurement request model
# ---------------------------------------------------------------------------

class ProcurementRequestModel(BaseModel):
    """Structured input from the buyer form (all USD)."""
    item: str
    category: str = "furniture"
    quantity: int = 50
    budget_usd: float = 15000.0
    deadline: str | None = None
    target_price_usd: float | None = None
    min_warranty_yrs: float = 1.0
    priority: str = "balanced"
    requirements: str = ""

    # Legacy compat
    goal: str | None = None


# ---------------------------------------------------------------------------
# Legacy helper — subprocess-based pipeline runner
# ---------------------------------------------------------------------------

async def run_script(cmd_list, cwd):
    """Run a subprocess and yield stdout lines as SSE data (async).

    Uses asyncio subprocess so lines stream to the client in real-time
    instead of buffering until the process finishes.
    """
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"

    process = await asyncio.create_subprocess_exec(
        *cmd_list,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=cwd,
        env=env,
    )
    while True:
        line = await process.stdout.readline()
        if not line:
            break
        yield f"data: {line.decode('utf-8', errors='replace')}\n\n"
    await process.wait()


# ---------------------------------------------------------------------------
# Main pipeline endpoint — in-process agent + EventBus -> structured JSON SSE
# ---------------------------------------------------------------------------

from core.events import EventBus


def _default_deadline() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")


def _build_request(req: ProcurementRequestModel):
    """Translate the API model into a core ProcurementRequest."""
    from core.types import ProcurementRequest, Priority

    try:
        priority = Priority(req.priority)
    except ValueError:
        priority = Priority.BALANCED
    return ProcurementRequest(
        item=req.item or "Ergonomic Office Chair",
        category=req.category or "furniture",
        quantity=req.quantity,
        budget_usd=req.budget_usd,
        deadline=req.deadline or _default_deadline(),
        target_price_usd=req.target_price_usd,
        min_warranty_yrs=req.min_warranty_yrs,
        priority=priority,
        requirements=req.requirements,
    )


def _prepare_environment() -> None:
    """Run the same setup demo.py does (DB, seed, buyer wallet, escrow, USDC).

    Blocking — call inside an executor thread. Emits coarse setup_log events.
    """
    import demo

    EventBus.emit("setup_log", {"message": "Initializing database & marketplace..."})
    demo.init_database()
    demo.seed_suppliers()
    demo.ensure_buyer_agent()
    EventBus.emit("setup_log", {"message": "Verifying escrow & funding buyer (USDC)..."})
    deploy_config = demo.verify_escrow()
    demo.ensure_buyer_usdc(deploy_config)


@app.post("/api/run_pipeline")
async def run_pipeline_endpoint(req: ProcurementRequestModel):
    """Run the autonomous buyer agent IN-PROCESS, streaming structured JSON
    events over SSE via the EventBus (no subprocess, no stdout parsing).

    Each SSE `data:` line is a JSON object `{"event": <type>, "data": {...}}`,
    except the terminal `data: [DONE]`.
    """
    cwd = str(ROOT)

    # Pre-clean DB for a fresh demo run
    db_path = ROOT / "db" / "hackathon.db"
    if db_path.exists():
        try:
            db_path.unlink()
        except OSError:
            pass

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    sentinel = object()

    def listener(event_type: str, data: dict) -> None:
        # Runs in the worker thread; hand off to the event loop thread-safely.
        try:
            msg = json.dumps({"event": event_type, "data": data}, default=str)
        except (TypeError, ValueError):
            msg = json.dumps({"event": event_type, "data": {}})
        loop.call_soon_threadsafe(queue.put_nowait, msg)

    def work() -> None:
        try:
            from agents.buyer.agent import run_buyer_agent

            EventBus.emit("setup_log", {"message": "Deploying smart contracts to Algorand Testnet..."})
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUNBUFFERED"] = "1"
            import subprocess
            subprocess.run(["python", "contracts/deploy.py"], cwd=cwd, env=env, check=False)

            _prepare_environment()
            request = _build_request(req)

            EventBus.emit("setup_log", {"message": "Launching autonomous procurement agent..."})
            run_buyer_agent("demo-buyer-agent", request)
        except Exception as e:  # never leave the stream hanging
            EventBus.emit(
                "agent_error",
                {"error_type": type(e).__name__, "message": str(e), "details": {}},
            )
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, sentinel)

    async def generate():
        EventBus.subscribe(listener)
        loop.run_in_executor(None, work)
        try:
            while True:
                item = await queue.get()
                if item is sentinel:
                    break
                yield f"data: {item}\n\n"
        finally:
            EventBus.unsubscribe(listener)
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


# Legacy subprocess + stdout pipeline — proven fallback. The frontend uses the
# in-process /api/run_pipeline above; if that misbehaves on a given environment,
# point the frontend at /api/run_pipeline_legacy as a one-line revert.
@app.post("/api/run_pipeline_legacy")
async def run_pipeline_legacy_endpoint(req: ProcurementRequestModel):
    cwd = str(ROOT)
    db_path = ROOT / "db" / "hackathon.db"
    if db_path.exists():
        try:
            db_path.unlink()
        except OSError:
            pass

    async def generate():
        yield "data: => [1/2] Deploying Smart Contracts...\n\n"
        async for chunk in run_script(["python", "contracts/deploy.py"], cwd):
            yield chunk
        yield "data: \n\n"
        yield "data: => [2/2] Running Autonomous Procurement Agent...\n\n"
        cmd = ["python", "demo.py"]
        if req.goal and not req.item:
            cmd.extend(["--goal", req.goal])
        else:
            cmd.extend(["--item", req.item])
            cmd.extend(["--category", req.category])
            cmd.extend(["--quantity", str(req.quantity)])
            cmd.extend(["--budget", str(req.budget_usd)])
            if req.deadline:
                cmd.extend(["--deadline", req.deadline])
            if req.target_price_usd is not None:
                cmd.extend(["--target-price", str(req.target_price_usd)])
            cmd.extend(["--min-warranty", str(req.min_warranty_yrs)])
            cmd.extend(["--priority", req.priority])
            if req.requirements:
                cmd.extend(["--requirements", req.requirements])
        async for chunk in run_script(cmd, cwd):
            yield chunk
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


# ---------------------------------------------------------------------------
# Funds release endpoint
# ---------------------------------------------------------------------------

@app.post("/api/release_funds")
async def release_funds_endpoint():
    """Trigger delivery proof and payment release."""
    cwd = str(ROOT)

    async def generate():
        yield "data: => Triggering Funds Release...\n\n"
        async for chunk in run_script(["python", "release_funds.py"], cwd):
            yield chunk
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


# ---------------------------------------------------------------------------
# Negotiation state endpoint (for frontend polling)
# ---------------------------------------------------------------------------

@app.get("/api/negotiation/{rfq_id}")
async def get_negotiation_state(rfq_id: str):
    """Return current negotiation state for an RFQ."""
    import sqlite3

    db_path = os.getenv("DATABASE_PATH", "db/hackathon.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    sessions = conn.execute(
        "SELECT * FROM negotiation_sessions WHERE rfq_id = ?", (rfq_id,)
    ).fetchall()

    result = []
    for s in sessions:
        rounds = conn.execute(
            "SELECT * FROM negotiation_rounds WHERE session_id = ? ORDER BY round_number, created_at",
            (s["session_id"],),
        ).fetchall()

        result.append({
            "session_id": s["session_id"],
            "supplier_id": s["supplier_id"],
            "phase": s["phase"],
            "current_round": s["current_round"],
            "max_rounds": s["max_rounds"],
            "rounds": [dict(r) for r in rounds],
        })

    conn.close()
    return {"rfq_id": rfq_id, "sessions": result}


# ---------------------------------------------------------------------------
# Serve frontend static files (must be AFTER all /api routes)
# ---------------------------------------------------------------------------
from fastapi.staticfiles import StaticFiles

frontend_dist = ROOT / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
