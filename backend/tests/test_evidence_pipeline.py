import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evidence import (  # noqa: E402
    EvidenceError,
    canonical_s3_url,
    create_presigned_upload,
    detect_image_content_type,
    generate_object_key,
    resolve_content_type,
    resolve_evidence_location,
    validate_declared_size,
    verify_uploaded_object,
)
from remote import build_aegis_payload  # noqa: E402

BUCKET = "aws-s3-877791042657-us-east-1-an"
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 20
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20


class FakeBody:
    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data


class FakeS3:
    def __init__(self, objects=None):
        self.objects = objects or {}
        self.presign_params = None

    def generate_presigned_url(self, client_method, Params, ExpiresIn):
        self.presign_params = Params
        return f"https://{Params['Bucket']}.s3.amazonaws.com/{Params['Key']}?X-Amz-Signature=redacted"

    def head_object(self, Bucket, Key):
        obj = self.objects[(Bucket, Key)]
        return {"ContentLength": obj["size"], "ContentType": obj["content_type"]}

    def get_object(self, Bucket, Key, Range=None):
        obj = self.objects[(Bucket, Key)]
        return {"Body": FakeBody(obj["bytes"][:16])}


class ContentTypeTests(unittest.TestCase):
    def test_jpeg_from_mime(self):
        self.assertEqual(resolve_content_type("image/jpeg", "photo.jpg"), "image/jpeg")

    def test_png_from_mime(self):
        self.assertEqual(resolve_content_type("image/png", "photo.png"), "image/png")

    def test_jpeg_from_extension_when_mime_missing(self):
        self.assertEqual(resolve_content_type("", "return.jpeg"), "image/jpeg")

    def test_rejects_heic_mime(self):
        with self.assertRaises(EvidenceError) as ctx:
            resolve_content_type("image/heic", "img.heic")
        self.assertEqual(ctx.exception.code, "EVIDENCE_UNSUPPORTED_FORMAT")
        self.assertIn("JPEG and PNG", ctx.exception.message)

    def test_rejects_heif_mime(self):
        with self.assertRaises(EvidenceError) as ctx:
            resolve_content_type("image/heif", "img.heif")
        self.assertEqual(ctx.exception.code, "EVIDENCE_UNSUPPORTED_FORMAT")

    def test_rejects_webp(self):
        with self.assertRaises(EvidenceError):
            resolve_content_type("image/webp", "img.webp")

    def test_rejects_zero_byte(self):
        with self.assertRaises(EvidenceError) as ctx:
            validate_declared_size(0)
        self.assertEqual(ctx.exception.code, "EVIDENCE_EMPTY")


class KeyAndUrlTests(unittest.TestCase):
    def test_key_format_jpeg(self):
        key = generate_object_key("TEST-CLAIM-001", "image/jpeg", "uploads")
        self.assertTrue(key.startswith("uploads/TEST-CLAIM-001/"))
        self.assertTrue(key.endswith(".jpg"))
        self.assertNotIn("test.jpg", key)
        self.assertNotIn("evidence/", key)

    def test_key_format_png(self):
        key = generate_object_key("TEST-CLAIM-001", "image/png", "uploads")
        self.assertTrue(key.endswith(".png"))

    def test_prefix_evidence_is_forced_to_uploads(self):
        key = generate_object_key("CLAIM-123", "image/jpeg", "evidence")
        self.assertTrue(key.startswith("uploads/CLAIM-123/"))

    def test_canonical_url(self):
        url = canonical_s3_url(BUCKET, "uploads/TEST-CLAIM-001/unique-image.jpg")
        self.assertEqual(url, f"s3://{BUCKET}/uploads/TEST-CLAIM-001/unique-image.jpg")


class ResolveLocationTests(unittest.TestCase):
    def test_missing_image(self):
        with self.assertRaises(EvidenceError) as ctx:
            resolve_evidence_location({}, BUCKET)
        self.assertEqual(ctx.exception.code, "EVIDENCE_MISSING")

    def test_rejects_https(self):
        with self.assertRaises(EvidenceError) as ctx:
            resolve_evidence_location({"s3_url": "https://cdn.example.com/images/a.jpg"}, BUCKET)
        self.assertEqual(ctx.exception.code, "EVIDENCE_INVALID_URL")

    def test_rejects_cloudfront(self):
        with self.assertRaises(EvidenceError):
            resolve_evidence_location(
                {"s3_url": "https://d111111abcdef8.cloudfront.net/uploads/a.jpg"},
                BUCKET,
            )

    def test_rejects_evidence_prefix(self):
        with self.assertRaises(EvidenceError) as ctx:
            resolve_evidence_location(
                {"s3_key": "evidence/CLAIM-123/abc.jpg"},
                BUCKET,
            )
        self.assertIn("uploads/", ctx.exception.message)

    def test_accepts_exact_s3_url(self):
        key = "uploads/TEST-CLAIM-001/unique-image.jpg"
        bucket, got_key, url = resolve_evidence_location(
            {"s3_url": f"s3://{BUCKET}/{key}"},
            BUCKET,
        )
        self.assertEqual(bucket, BUCKET)
        self.assertEqual(got_key, key)
        self.assertEqual(url, f"s3://{BUCKET}/{key}")

    def test_accepts_bare_key(self):
        bucket, key, url = resolve_evidence_location(
            {"s3_image_url": "uploads/CLAIM-123/abc.jpg"},
            BUCKET,
        )
        self.assertEqual(key, "uploads/CLAIM-123/abc.jpg")
        self.assertEqual(url, f"s3://{BUCKET}/uploads/CLAIM-123/abc.jpg")


class PresignAndAegisEqualityTests(unittest.TestCase):
    def test_jpeg_upload_key_equals_aegis_s3_url(self):
        s3 = FakeS3()
        ticket = create_presigned_upload(
            s3,
            {
                "claim_id": "TEST-CLAIM-001",
                "content_type": "image/jpeg",
                "filename": "unique-image.jpg",
                "content_length": 1024,
            },
            BUCKET,
            "uploads",
        )
        self.assertEqual(s3.presign_params["ContentType"], "image/jpeg")
        self.assertEqual(s3.presign_params["Bucket"], BUCKET)
        self.assertEqual(s3.presign_params["Key"], ticket["s3_key"])
        self.assertTrue(ticket["s3_key"].startswith("uploads/TEST-CLAIM-001/"))
        self.assertTrue(ticket["s3_key"].endswith(".jpg"))
        self.assertNotEqual(ticket["s3_key"], "uploads/test.jpg")
        self.assertEqual(ticket["s3_url"], f"s3://{BUCKET}/{ticket['s3_key']}")

        aegis = build_aegis_payload(
            "TEST-CLAIM-001",
            {
                "customer_text": "The screen arrived cracked.",
                "product_category": "electronics",
                "order_value_usd": 299.99,
            },
            ticket["s3_url"],
        )
        self.assertEqual(aegis["s3_url"], ticket["s3_url"])
        self.assertEqual(aegis["s3_url"], canonical_s3_url(BUCKET, ticket["s3_key"]))
        self.assertNotIn("test.jpg", aegis["s3_url"])
        self.assertEqual(aegis["claim_id"], "TEST-CLAIM-001")

    def test_png_upload_uses_png_content_type(self):
        s3 = FakeS3()
        ticket = create_presigned_upload(
            s3,
            {
                "claim_id": "TEST-CLAIM-001",
                "content_type": "image/png",
                "filename": "test.png",
                "content_length": 2048,
            },
            BUCKET,
            "uploads",
        )
        self.assertEqual(s3.presign_params["ContentType"], "image/png")
        self.assertEqual(ticket["content_type"], "image/png")
        self.assertTrue(ticket["s3_key"].endswith(".png"))
        aegis = build_aegis_payload("TEST-CLAIM-001", {"message": "ok"}, ticket["s3_url"])
        self.assertEqual(aegis["s3_url"], ticket["s3_url"])

    def test_explicit_unique_key_passed_through_unchanged(self):
        s3_url = f"s3://{BUCKET}/uploads/TEST-CLAIM-001/unique-image.jpg"
        aegis = build_aegis_payload(
            "TEST-CLAIM-001",
            {"customer_text": "The screen arrived cracked."},
            s3_url,
        )
        self.assertEqual(aegis["s3_url"], s3_url)


class VerifyObjectTests(unittest.TestCase):
    def test_verifies_jpeg_magic_and_size(self):
        key = "uploads/TEST-CLAIM-001/unique-image.jpg"
        s3 = FakeS3({
            (BUCKET, key): {
                "size": len(JPEG_BYTES),
                "content_type": "image/jpeg",
                "bytes": JPEG_BYTES,
            }
        })
        result = verify_uploaded_object(s3, BUCKET, key, "image/jpeg")
        self.assertEqual(result["content_type"], "image/jpeg")
        self.assertGreater(result["content_length"], 0)

    def test_verifies_png_magic(self):
        key = "uploads/TEST-CLAIM-001/test.png"
        s3 = FakeS3({
            (BUCKET, key): {
                "size": len(PNG_BYTES),
                "content_type": "image/png",
                "bytes": PNG_BYTES,
            }
        })
        result = verify_uploaded_object(s3, BUCKET, key, "image/png")
        self.assertEqual(result["content_type"], "image/png")

    def test_rejects_empty_object(self):
        key = "uploads/TEST-CLAIM-001/empty.jpg"
        s3 = FakeS3({
            (BUCKET, key): {"size": 0, "content_type": "image/jpeg", "bytes": b""}
        })
        with self.assertRaises(EvidenceError) as ctx:
            verify_uploaded_object(s3, BUCKET, key, "image/jpeg")
        self.assertEqual(ctx.exception.code, "EVIDENCE_EMPTY")

    def test_detect_magic(self):
        self.assertEqual(detect_image_content_type(JPEG_BYTES), "image/jpeg")
        self.assertEqual(detect_image_content_type(PNG_BYTES), "image/png")
        self.assertIsNone(detect_image_content_type(b"not-an-image"))


class NoFixtureFallbackTests(unittest.TestCase):
    def test_backend_never_assigns_test_jpg(self):
        src_dir = Path(__file__).resolve().parents[1] / "src"
        for path in src_dir.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn('= "uploads/test.jpg"', text)
            self.assertNotIn("= 'uploads/test.jpg'", text)
            self.assertNotIn("uploads/placeholder.jpg", text)

    def test_frontend_has_no_test_jpg_fallback(self):
        root = Path(__file__).resolve().parents[2]
        claims_api = (root / "src" / "services" / "claimsApi.ts").read_text(encoding="utf-8")
        self.assertNotIn("test.jpg", claims_api)


if __name__ == "__main__":
    unittest.main()
