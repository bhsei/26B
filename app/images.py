import warnings
from io import BytesIO

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.errors import AppError


def prepare_image(upload: UploadFile, max_bytes: int) -> bytes:
    """Decode and re-encode: remove metadata; never store the original photo."""
    try:
        data = upload.file.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise AppError(413, "Photo exceeds the 5 MiB limit.", "IMAGE_TOO_LARGE")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as original:
                if original.format not in {"JPEG", "PNG", "WEBP"}:
                    raise AppError(
                        415, "Use a JPEG, PNG or WebP photo.", "UNSUPPORTED_IMAGE_FORMAT"
                    )
                if original.width * original.height > 20_000_000:
                    raise AppError(
                        413, "Photo exceeds 20 megapixels.", "IMAGE_DIMENSIONS_TOO_LARGE"
                    )
                original.load()
                processed = ImageOps.exif_transpose(original).convert("RGB")
                processed.thumbnail((1024, 1024))
                output = BytesIO()
                processed.save(output, format="JPEG", quality=85)
                return output.getvalue()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise AppError(415, "Invalid or unsupported image.", "INVALID_IMAGE") from None
    finally:
        upload.file.close()
