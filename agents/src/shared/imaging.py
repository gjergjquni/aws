"""Pillow work for claim evidence photos.

Three jobs: pull EXIF out before it is destroyed by re-encoding, turn that EXIF
into the summary and problem flags the response contract promises, and produce a
bounded JPEG suitable for both the Hive API and Bedrock. Everything here runs on
attacker-controlled bytes, so the decompression-bomb ceiling is explicit and
every parse is wrapped.

Metadata problems are detected in code rather than asked of the vision model.
Reading tags is exact work with a right answer, and a model paraphrasing EXIF it
was handed as text produces a different wording of the same finding every run —
useless for a UI that wants to filter on a flag.
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageOps, UnidentifiedImageError
from PIL.ExifTags import GPSTAGS, TAGS

from . import config
from .errors import EVIDENCE_INVALID_IMAGE, EvidenceError

logger = config.get_logger(__name__)

# Pillow's default (~89M pixels) only warns. A 15 MB upload cannot legitimately
# decode to more than this, and refusing outright avoids the memory blow-up.
Image.MAX_IMAGE_PIXELS = 50_000_000

MAX_DIMENSION = 1024
JPEG_QUALITY = 85

# Tags whose values are long binary blobs that add prompt tokens and no signal.
_SKIP_TAGS = {"MakerNote", "UserComment", "PrintImageMatching", "ImageResources"}

# Substring of the Software tag -> reported flag. An editor tag is not proof of
# fraud (phones run their own processing pipelines) but it is the difference
# between a camera original and a file that has been through a pixel editor.
_EDITOR_SIGNATURES = (
    ("photoshop", "edited_in_photoshop"),
    ("lightroom", "edited_in_lightroom"),
    ("gimp", "edited_in_gimp"),
    ("affinity", "edited_in_affinity_photo"),
    ("pixelmator", "edited_in_pixelmator"),
    ("paint.net", "edited_in_paint_net"),
    ("snapseed", "edited_in_snapseed"),
    ("facetune", "edited_in_facetune"),
    ("picsart", "edited_in_picsart"),
    ("canva", "edited_in_canva"),
    ("pixlr", "edited_in_pixlr"),
    ("inpaint", "edited_with_inpainting_tool"),
    ("cleanup.pictures", "edited_with_inpainting_tool"),
)

# Generators that label their own output. Cheap to check and conclusive when hit.
_AI_SIGNATURES = (
    "dall-e",
    "dalle",
    "midjourney",
    "stable diffusion",
    "stablediffusion",
    "automatic1111",
    "comfyui",
    "firefly",
    "imagen",
    "flux",
    "invokeai",
    "novelai",
)

# EXIF stores local time with no zone, so a photo taken in UTC+14 can legitimately
# look up to a day ahead of our clock.
_CLOCK_SKEW = timedelta(days=1)

_EXIF_TIME_FORMATS = ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y:%m:%d %H:%M")


def extract_exif(path: str) -> Dict[str, Any]:
    """Extract readable EXIF tags, including GPS, into a JSON-safe dict.

    Corrupt or absent metadata is itself a fraud signal, so this reports what
    happened instead of failing the analysis.
    """
    metadata: Dict[str, Any] = {}
    try:
        with Image.open(path) as image:
            raw = image.getexif()
            if not raw:
                return {"note": "No EXIF metadata present"}

            for tag_id, value in raw.items():
                name = TAGS.get(tag_id, str(tag_id))
                if name in _SKIP_TAGS:
                    continue
                metadata[name] = _stringify(value)

            try:
                gps = raw.get_ifd(0x8825)
            except (KeyError, AttributeError, OSError):
                gps = None
            if gps:
                metadata["GPSInfo"] = {
                    GPSTAGS.get(key, str(key)): _stringify(value) for key, value in gps.items()
                }
    except Exception as exc:
        logger.warning("EXIF extraction failed: %s", exc)
        return {"note": f"EXIF extraction failed: {exc}"}
    return metadata or {"note": "No EXIF metadata present"}


def _stringify(value: Any) -> str:
    text = str(value)
    return text[:512]


def _tag(metadata: Dict[str, Any], *names: str) -> Optional[str]:
    """First non-empty value among the given tag names."""
    for name in names:
        value = metadata.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _parse_exif_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    trimmed = value.strip()
    for pattern in _EXIF_TIME_FORMATS:
        try:
            return datetime.strptime(trimmed, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _has_real_tags(metadata: Dict[str, Any]) -> bool:
    """True when extraction found actual tags rather than only its own note."""
    return any(key != "note" for key in metadata)


def redact_exif_for_prompt(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Drop GPS and oversized blobs before metadata is sent to a model."""
    redacted = dict(metadata)
    redacted.pop("GPSInfo", None)
    redacted.pop("GPSLatitude", None)
    redacted.pop("GPSLongitude", None)
    return redacted


def summarize_exif(metadata: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Reduce raw EXIF to the three fields the response contract publishes.

    ``None`` means the tag was absent, which is itself a finding — distinct from
    a string saying "unknown", which a UI would render as if the camera had
    reported it.
    """
    make = _tag(metadata, "Make")
    model = _tag(metadata, "Model")
    if make and model:
        # Canon writes "Canon" in both tags; "Canon Canon EOS R6" reads as a bug.
        camera = model if model.lower().startswith(make.lower()) else f"{make} {model}"
    else:
        camera = make or model

    return {
        "camera": camera,
        "timestamp": _tag(metadata, "DateTimeOriginal", "DateTimeDigitized", "DateTime"),
        "software": _tag(metadata, "Software", "ProcessingSoftware"),
    }


def detect_metadata_problems(metadata: Dict[str, Any]) -> List[str]:
    """Flags derived from EXIF, as stable tokens a UI can filter on."""
    problems: List[str] = []

    note = metadata.get("note")
    if isinstance(note, str) and note.startswith("EXIF extraction failed"):
        return ["exif_extraction_failed"]

    if not _has_real_tags(metadata):
        # Stripped metadata is the single most common sign of a reused or
        # downloaded image: every social platform and messaging app removes it.
        return ["missing_exif"]

    summary = summarize_exif(metadata)

    if not summary["camera"]:
        problems.append("no_camera_make")
    if not summary["timestamp"]:
        problems.append("no_original_timestamp")

    software = (summary["software"] or "").lower()
    if software:
        if any(signature in software for signature in _AI_SIGNATURES):
            problems.append("ai_tool_in_metadata")
        for signature, flag in _EDITOR_SIGNATURES:
            if signature in software and flag not in problems:
                problems.append(flag)

    taken = _parse_exif_datetime(summary["timestamp"])
    if taken and taken > datetime.now(timezone.utc) + _CLOCK_SKEW:
        problems.append("future_timestamp")

    return problems


def to_bounded_jpeg(path: str) -> Tuple[bytes, Dict[str, int]]:
    """Re-encode to a JPEG no larger than 1024x1024, honouring EXIF rotation.

    Returns the encoded bytes and the original pixel dimensions. Rotation is
    applied first so the model sees the photo the way a person would.
    """
    from .image_forensics import assert_supported_container

    with open(path, "rb") as handle:
        header = handle.read(32)
    assert_supported_container(header, name="image")

    try:
        with Image.open(path) as image:
            image.load()
            original = {"width": image.width, "height": image.height}
            image = ImageOps.exif_transpose(image)
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    except UnidentifiedImageError as exc:
        raise EvidenceError(EVIDENCE_INVALID_IMAGE, "Uploaded file is not a readable image") from exc
    except Image.DecompressionBombError as exc:
        raise EvidenceError(EVIDENCE_INVALID_IMAGE, "Image dimensions exceed the supported maximum") from exc
    except OSError as exc:
        raise EvidenceError(EVIDENCE_INVALID_IMAGE, f"Image could not be decoded: {exc}") from exc

    return buffer.getvalue(), original
