from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import pathlib
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "AgentTrade API is active"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

class PipelineRequest(BaseModel):
    goal: str

def run_script(cmd_list, cwd):
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
        encoding="utf-8"
    )
    for line in iter(process.stdout.readline, ''):
        yield f"data: {line}\n\n"
    process.stdout.close()
    process.wait()

@app.post("/api/run_pipeline")
async def run_pipeline_endpoint(req: PipelineRequest):
    cwd = pathlib.Path(__file__).parent.absolute()
    
    # Pre-clean DB
    db_path = cwd / "db" / "hackathon.db"
    if db_path.exists():
        try:
            db_path.unlink()
        except Exception:
            pass

    def generate():
        yield "data: => [1/2] Deploying Smart Contracts...\n\n"
        yield from run_script(["python", "contracts/deploy.py"], str(cwd))
        
        yield "data: \n\n"
        yield "data: => [2/2] Running Autonomous Pipeline...\n\n"
        yield from run_script(["python", "demo.py", "--goal", req.goal], str(cwd))
        
        yield "data: [DONE]\n\n"
        
    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/api/release_funds")
async def release_funds_endpoint():
    cwd = pathlib.Path(__file__).parent.absolute()
    
    def generate():
        yield "data: => Triggering Funds Release...\n\n"
        yield from run_script(["python", "release_funds.py"], str(cwd))
        yield "data: [DONE]\n\n"
        
    return StreamingResponse(generate(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
