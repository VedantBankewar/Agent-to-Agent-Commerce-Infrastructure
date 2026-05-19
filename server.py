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
import subprocess
import sys
import threading
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
    load_dotenv(ROOT / ".env")
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

def run_script(cmd_list, cwd):
    """Run a subprocess and yield stdout lines as SSE data."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"

    process = subprocess.Popen(
        cmd_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=cwd,
        env=env,
        encoding="utf-8",
    )
    for line in iter(process.stdout.readline, ""):
        yield f"data: {line}\n\n"
    process.stdout.close()
    process.wait()


# ---------------------------------------------------------------------------
# Main pipeline endpoint — EventBus SSE streaming
# ---------------------------------------------------------------------------

@app.post("/api/run_pipeline")
async def run_pipeline_endpoint(req: ProcurementRequestModel):
    """Run the autonomous buyer agent, streaming events via SSE.

    Accepts either structured fields or a legacy `goal` string.
    """
    cwd = str(ROOT)

    # Pre-clean DB for fresh demo run
    db_path = ROOT / "db" / "hackathon.db"
    if db_path.exists():
        try:
            db_path.unlink()
        except Exception:
            pass

    async def generate():
        # Phase 1: Deploy contracts
        yield "data: => [1/2] Deploying Smart Contracts...\n\n"
        for chunk in run_script(["python", "contracts/deploy.py"], cwd):
            yield chunk

        yield "data: \n\n"
        yield "data: => [2/2] Running Autonomous Procurement Agent...\n\n"

        # Build command args
        cmd = ["python", "demo.py"]

        if req.goal and not req.item:
            # Legacy mode
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

        for chunk in run_script(cmd, cwd):
            yield chunk

        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Funds release endpoint
# ---------------------------------------------------------------------------

@app.post("/api/release_funds")
async def release_funds_endpoint():
    """Trigger delivery proof and payment release."""
    cwd = str(ROOT)

    def generate():
        yield "data: => Triggering Funds Release...\n\n"
        yield from run_script(["python", "release_funds.py"], cwd)
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
