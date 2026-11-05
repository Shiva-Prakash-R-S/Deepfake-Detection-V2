import os
import uuid
import hashlib
import io
from PIL import Image
from werkzeug.utils import secure_filename
from backend.config import Config

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "BMP"}


def get_secure_upload_dir() -> str:
    """Return the absolute path to the prediction uploads directory."""
    predictions_dir = os.path.join(Config.UPLOAD_FOLDER, "predictions")
    os.makedirs(predictions_dir, exist_ok=True)
    return predictions_dir


def validate_and_save_image(file_storage, user_id: int):
    """
    Validate and securely save an uploaded image file.

    Returns:
        tuple: (
            relative_stored_path: str,
            sha256_hash: str,
            image_format: str,
            width: int,
            height: int,
            raw_bytes: bytes,
            safe_original_name: str
        )
    """
    safe_original_name = secure_filename(file_storage.filename) or "uploaded_image.jpg"
    raw_bytes = file_storage.read()

    if not raw_bytes or len(raw_bytes) == 0:
        raise ValueError("Uploaded image file is empty.")

    # Calculate SHA-256
    sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

    # Validate image format and dimensions using PIL
    try:
        img_verify = Image.open(io.BytesIO(raw_bytes))
        img_verify.verify()
    except Exception as e:
        raise ValueError(f"Invalid or corrupted image file: {str(e)}")

    # Re-open to read format and dimensions
    img = Image.open(io.BytesIO(raw_bytes))
    width, height = img.size
    img_format = (img.format or "JPEG").upper()

    if img_format not in ALLOWED_FORMATS:
        raise ValueError(f"Unsupported image format: {img_format}. Allowed: {', '.join(ALLOWED_FORMATS)}")

    # Determine extension
    ext_map = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "BMP": ".bmp"}
    ext = ext_map.get(img_format, ".jpg")

    # Secure unique storage filename: <user_id>_<uuid4><ext>
    unique_filename = f"user_{user_id}_{uuid.uuid4().hex}{ext}"
    upload_dir = get_secure_upload_dir()
    destination_path = os.path.join(upload_dir, unique_filename)

    # Save to disk
    with open(destination_path, "wb") as f:
        f.write(raw_bytes)

    # Store relative path
    relative_path = os.path.join("predictions", unique_filename).replace("\\", "/")

    return (
        relative_path,
        sha256_hash,
        img_format,
        width,
        height,
        raw_bytes,
        safe_original_name
    )


def resolve_stored_image_path(stored_relative_path: str) -> str:
    """
    Safely resolve a stored relative image path and guard against path traversal.
    """
    base_dir = os.path.abspath(Config.UPLOAD_FOLDER)
    target_path = os.path.abspath(os.path.join(base_dir, stored_relative_path))

    # Path traversal check
    if not target_path.startswith(base_dir):
        raise PermissionError("Access denied: Invalid path traversal detected.")

    if not os.path.isfile(target_path):
        raise FileNotFoundError("Requested prediction image file was not found on disk.")

    return target_path


def remove_stored_image(stored_relative_path: str) -> None:
    """Clean up stored image file if database transaction fails."""
    try:
        abs_path = resolve_stored_image_path(stored_relative_path)
        if os.path.exists(abs_path):
            os.remove(abs_path)
    except Exception:
        pass
