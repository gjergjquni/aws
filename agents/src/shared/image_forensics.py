"""Deterministic image-analysis signals that do not require an LLM or Rekognition.

Perceptual hashes detect duplicates/near-duplicates. Dimension and format checks
are exact. Missing metadata is reported by imaging.py, not guessed here.
"""

from __future__ import annotations

import hashlib
import io
from typing import Any, Dict, List, Mapping, Sequence

from PIL import Image, UnidentifiedImageError

from . import config
from .errors import EVIDENCE_EMPTY, EVIDENCE_INVALID_IMAGE, EVIDENCE_UNSUPPORTED_FORMAT, EvidenceError, ValidationError

logger = config.get_logger(__name__)

SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF", "BMP", "TIFF"}
HAMMING_DUPLICATE_THRESHOLD = 8

_HEIC_BRANDS = {b"heic", b"heix", b"heif", b"hevc", b"hevx", b"mif1", b"msf1"}


def sniff_container(data: bytes) -> str:
    """Identify the file container from magic bytes. Does not decode pixels."""
    if not data:
        return "empty"
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:2] == b"BM":
        return "bmp"
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12].lower()
        if brand in _HEIC_BRANDS:
            return "heic"
        if brand == b"avif":
            return "avif"
    return "unknown"


def _reject_unsupported(kind: str, name: str) -> None:
    if kind in {"heic", "avif"}:
        raise EvidenceError(
            EVIDENCE_UNSUPPORTED_FORMAT,
            (
                f"{name} is {kind.upper()}, which this runtime cannot decode "
                "(Pillow on Lambda has no libheif). Re-encode to JPEG or PNG before upload."
            ),
        )


def assert_supported_container(data: bytes, name: str = "image") -> str:
    """Sniff magic bytes and refuse HEIC/AVIF before Pillow tries to open them."""
    kind = sniff_container(data)
    if kind == "empty":
        raise EvidenceError(EVIDENCE_EMPTY, f"{name} is empty")
    _reject_unsupported(kind, name)
    return kind


def file_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inspect_bytes(data: bytes, name: str = "image") -> Dict[str, Any]:
    """Return format, dimensions, mode, and perceptual hashes for one image."""
    if not data:
        raise EvidenceError(EVIDENCE_EMPTY, f"{name} is empty")
    if len(data) > config.max_image_bytes():
        raise EvidenceError(
            EVIDENCE_INVALID_IMAGE,
            f"{name} exceeds the {config.max_image_bytes()} byte limit",
        )
    kind = sniff_container(data)
    _reject_unsupported(kind, name)
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            fmt = (image.format or "").upper()
            if fmt not in SUPPORTED_FORMATS:
                raise EvidenceError(
                    EVIDENCE_UNSUPPORTED_FORMAT,
                    f"{name} format {fmt or kind or 'unknown'} is not supported",
                )
            width, height = image.size
            mode = image.mode
            gray = image.convert("L").resize((32, 32), Image.Resampling.LANCZOS)
            sample = list(gray.getdata())
            low_texture = (max(sample) - min(sample)) < 8
            ahash = average_hash(image)
            dhash = difference_hash(image)
    except EvidenceError:
        raise
    except UnidentifiedImageError as exc:
        raise EvidenceError(EVIDENCE_INVALID_IMAGE, f"{name} is not a readable image") from exc
    except ValidationError:
        raise
    except OSError as exc:
        raise EvidenceError(EVIDENCE_INVALID_IMAGE, f"{name} could not be decoded: {exc}") from exc

    return {
        "name": name,
        "byte_length": len(data),
        "sha256": file_digest(data),
        "format": fmt,
        "width": width,
        "height": height,
        "mode": mode,
        "average_hash": ahash,
        "difference_hash": dhash,
        "low_texture": low_texture,
        "tiny": width < 64 or height < 64,
        "extreme_aspect": (max(width, 1) / max(height, 1)) > 6 or (max(height, 1) / max(width, 1)) > 6,
    }


def average_hash(image: Image.Image, size: int = 8) -> str:
    gray = image.convert("L").resize((size, size), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    mean = sum(pixels) / len(pixels)
    bits = "".join("1" if pixel >= mean else "0" for pixel in pixels)
    return f"{int(bits, 2):0{size * size // 4}x}"


def difference_hash(image: Image.Image, size: int = 8) -> str:
    gray = image.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    bits = []
    for row in range(size):
        start = row * (size + 1)
        for col in range(size):
            bits.append("1" if pixels[start + col] > pixels[start + col + 1] else "0")
    joined = "".join(bits)
    return f"{int(joined, 2):0{size * size // 4}x}"


def hamming_hex(left: str, right: str) -> int:
    if not left or not right or len(left) != len(right):
        return 64
    return bin(int(left, 16) ^ int(right, 16)).count("1")


def duplicate_pairs(summaries: Sequence[Mapping]) -> List[Dict[str, Any]]:
    """Exact SHA-256 matches and near-duplicate perceptual hashes."""
    pairs: List[Dict[str, Any]] = []
    for i, left in enumerate(summaries):
        for j, right in enumerate(summaries):
            if j <= i:
                continue
            exact = left.get("sha256") and left.get("sha256") == right.get("sha256")
            distance = hamming_hex(str(left.get("difference_hash") or ""), str(right.get("difference_hash") or ""))
            near = distance <= HAMMING_DUPLICATE_THRESHOLD
            if near and not exact and (left.get("low_texture") or right.get("low_texture")):
                # Solid-color / low-detail frames share trivial hashes; do not treat as duplicates.
                continue
            if exact or near:
                pairs.append(
                    {
                        "left": i,
                        "right": j,
                        "exact": bool(exact),
                        "hamming": distance,
                    }
                )
    return pairs


def quality_findings(summary: Dict[str, Any], image_index: int) -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []
    label = image_index + 1
    findings.append(
        {
            "category": "QUALITY",
            "severity": "LOW",
            "description": (
                f"Image {label} is {summary['width']}x{summary['height']} "
                f"{summary['format']}, {summary['byte_length']} bytes"
            ),
            "evidence": f"format={summary['format']} mode={summary['mode']}",
            "source": "image_analysis",
        }
    )
    if summary.get("tiny"):
        findings.append(
            {
                "category": "QUALITY",
                "severity": "MEDIUM",
                "description": f"Image {label} is unusually small for product evidence",
                "evidence": f"{summary['width']}x{summary['height']}",
                "source": "image_analysis",
            }
        )
    if summary.get("extreme_aspect"):
        findings.append(
            {
                "category": "COMPRESSION",
                "severity": "LOW",
                "description": f"Image {label} has an extreme aspect ratio",
                "evidence": f"{summary['width']}x{summary['height']}",
                "source": "image_analysis",
            }
        )
    return findings


def duplicate_findings(pairs: Sequence[Mapping[str, Any]]) -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []
    for pair in pairs:
        kind = "exact duplicate" if pair.get("exact") else "near-duplicate"
        findings.append(
            {
                "category": "DUPLICATE",
                "severity": "HIGH" if pair.get("exact") else "MEDIUM",
                "description": (
                    f"Images {pair['left'] + 1} and {pair['right'] + 1} are {kind} evidence"
                ),
                "evidence": (
                    "identical SHA-256" if pair.get("exact") else f"dHash hamming={pair.get('hamming')}"
                ),
                "source": "image_analysis",
            }
        )
    return findings


def metadata_findings(problems: Sequence[str]) -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []
    for flag in problems:
        if flag == "missing_exif":
            severity, description = "LOW", "No EXIF metadata present (common after messaging-app recompression)"
        elif flag == "ai_tool_in_metadata":
            severity, description = "HIGH", "Software tag names a generative-image tool"
        elif flag.startswith("edited_"):
            severity, description = "MEDIUM", f"Software tag indicates editing: {flag}"
        elif flag == "future_timestamp":
            severity, description = "MEDIUM", "EXIF capture time is implausibly in the future"
        elif flag == "exif_extraction_failed":
            severity, description = "MEDIUM", "EXIF was present but could not be parsed"
        else:
            severity, description = "LOW", f"Metadata flag: {flag}"
        findings.append(
            {
                "category": "METADATA",
                "severity": severity,
                "description": description,
                "evidence": flag,
                "source": "metadata",
            }
        )
    return findings
