"""Manual test harness for ailacore.pocket — not a real AILa service.

Run locally (no Docker) to poke the Pocket API by hand via Swagger UI:

    pip install -r PocketPlayground/requirements.txt
    pip install -e Shared
    uvicorn PocketPlayground.main:app --reload --port 8099

then open http://127.0.0.1:8099/docs. Needs POCKET_API_KEY in
PocketPlayground/.env (see .env.example).
"""
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile

load_dotenv(Path(__file__).parent / ".env")

from ailacore import pocket  # noqa: E402 (must import after load_dotenv)

app = FastAPI(title="Pocket API playground")


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "pocket_base_url": pocket.POCKET_BASE_URL}


@app.get("/recordings")
async def recordings(
    page: int = 1,
    limit: int = 20,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    tag_ids: Optional[str] = None,
):
    return await pocket.list_recordings(
        page=page, limit=limit, start_date=start_date, end_date=end_date, tag_ids=tag_ids
    )


@app.get("/recordings/{recording_id}")
async def recording_detail(
    recording_id: str,
    include_transcript: bool = True,
    include_summarizations: bool = True,
):
    return await pocket.get_recording(
        recording_id,
        include_transcript=include_transcript,
        include_summarizations=include_summarizations,
    )


@app.post("/search")
async def search(query: str, limit: int = 8):
    return await pocket.search_recordings(query, limit=limit)


@app.get("/tags")
async def tags():
    return await pocket.list_tags()


@app.post("/recordings/upload")
async def upload_recording(file: UploadFile = File(...), title: Optional[str] = Form(None)):
    """Needs POCKET_UPLOAD_API_KEY, not POCKET_API_KEY — see .env.example."""
    audio_bytes = await file.read()
    created = await pocket.create_upload_url(
        title=title, content_type=file.content_type, file_name=file.filename
    )
    data = created.get("data") or {}
    upload_url = data.get("upload_url") or data.get("url")
    if not upload_url:
        return {"error": "Pocket nevrátil upload URL.", "raw": created}
    await pocket.upload_audio(upload_url, audio_bytes, file.content_type or "audio/webm")
    return {"uploaded": True, "raw": created}
