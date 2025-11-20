from fastapi import FastAPI
from app.orchestrator import run_general_command

app = FastAPI(title="General AI Agent")

class PromptIn(BaseModel):
    prompt: str

@app.post("/general")
async def general_command(data: PromptIn):
    return await run_general_command(data.prompt)