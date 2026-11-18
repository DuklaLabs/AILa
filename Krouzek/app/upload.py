"""Upload obrázků pro Kroužek (fotky žáků/projektů) — prototyp je ukládal
jako base64 přímo v localStorage; tady se místo toho soubor uloží na disk a
klient dostane zpátky /static URL, aby nerostl JSON v club.documents."""
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from ailacore.auth import require_role
from ailacore.models import User

PREFIX = os.getenv("URL_PREFIX", "").rstrip("/")

router = APIRouter(prefix="/api/club", tags=["club"])

_ALLOWED_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
_MAX_BYTES = 8 * 1024 * 1024
_UPLOAD_DIR = os.path.join("app", "static", "uploads")


@router.post("/upload")
async def upload_image(file: UploadFile, user: User = Depends(require_role("admin", "staff"))):
    ext = _ALLOWED_TYPES.get(file.content_type)
    if ext is None:
        raise HTTPException(status_code=400, detail="Unsupported image type")

    content = await file.read()
    if len(content) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large")

    os.makedirs(_UPLOAD_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    with open(os.path.join(_UPLOAD_DIR, filename), "wb") as f:
        f.write(content)

    return {"url": f"{PREFIX}/static/uploads/{filename}"}
