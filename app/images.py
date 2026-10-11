import warnings
from io import BytesIO

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError


def prepare_image(upload: UploadFile, max_bytes: int) -> bytes:
    """Decode and re-encode: remove metadata; never store the original photo."""
    try:
        data = upload.file.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise HTTPException(413, "Photo exceeds the 5 MiB limit.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as original:
                if original.format not in {"JPEG", "PNG", "WEBP"}:
                    raise HTTPException(415, "Use a JPEG, PNG or WebP photo.")
                if original.width * original.height > 20_000_000:
                    raise HTTPException(413, "Photo exceeds 20 megapixels.")
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
        raise HTTPException(415, "Invalid or unsupported image.") from None
    finally:
        upload.file.close()
