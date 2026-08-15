import re
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import BadRequest

ALLOWED_MIME = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/csv",
    "text/plain",
}

_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def safe_filename(name: str) -> str:
    cleaned = _SAFE.sub("_", Path(name).name)[:120]
    return cleaned or "file"


def save_upload(file: UploadFile, subdir: str) -> tuple[str, int]:
    """Store an upload under UPLOAD_DIR/subdir. Returns (relative_path, size_bytes)."""
    if file.content_type and file.content_type not in ALLOWED_MIME:
        raise BadRequest(f"Unsupported file type: {file.content_type}")

    data = file.file.read()
    if len(data) > settings.max_upload_bytes:
        raise BadRequest(f"File exceeds {settings.MAX_UPLOAD_SIZE_MB} MB limit")
    if not data:
        raise BadRequest("Uploaded file is empty")

    target_dir = Path(settings.UPLOAD_DIR) / subdir
    target_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}_{safe_filename(file.filename or 'file')}"
    path = target_dir / stored_name
    path.write_bytes(data)

    return str(Path(subdir) / stored_name).replace("\\", "/"), len(data)


def absolute_path(relative_path: str) -> Path:
    """Resolve a stored relative path, refusing anything that escapes UPLOAD_DIR."""
    root = Path(settings.UPLOAD_DIR).resolve()
    resolved = (root / relative_path).resolve()
    if not resolved.is_relative_to(root):
        raise BadRequest("Invalid file path")
    return resolved


def delete_file(relative_path: str) -> None:
    try:
        absolute_path(relative_path).unlink(missing_ok=True)
    except (OSError, BadRequest):
        pass
