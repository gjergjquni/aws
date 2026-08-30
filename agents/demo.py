"""Local run of Agent 1 (visual), Agent 2 (claim), then Agent 6.

    python demo.py
    python demo.py --real-aws
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load_dotenv() -> None:
    path = os.path.join(ROOT, ".env")
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def _make_image(path: str, color: tuple[int, int, int], *, with_exif: bool = True, stripe: int = 0) -> None:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (640, 480), color)
    draw = ImageDraw.Draw(image)
    if stripe:
        draw.rectangle([40, 40, 200, 200], fill=(255, 220, 40))
        draw.line([(0, stripe), (639, stripe + 80)], fill=(10, 10, 10), width=12)
        draw.text((48, 300), f"SKU-{stripe}", fill=(255, 255, 255))
    extra: Dict[str, Any] = {}
    if with_exif:
        exif = Image.Exif()
        exif[0x010F] = "DemoCam"
        exif[0x0110] = "Model Z"
        exif[0x0132] = "2026:03:01 12:00:00"
        extra["exif"] = exif
    image.save(path, "JPEG", quality=90, **extra)


def _probe_aws() -> Dict[str, Any]:
    status = {
        "credentials": False,
        "identity": None,
        "bedrock_model": os.environ.get("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0"),
        "embedding_model": os.environ.get("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"),
        "opensearch_endpoint": os.environ.get("OPENSEARCH_ENDPOINT", "").strip(),
        "error": None,
    }
    try:
        import boto3

        sts = boto3.client("sts")
        ident = sts.get_caller_identity()
        status["credentials"] = True
        status["identity"] = {
            "account": ident.get("Account"),
            "arn": ident.get("Arn"),
        }
    except Exception as exc:
        status["error"] = str(exc)
    return status


def _print_result(title: str, payload: Dict[str, Any]) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)
    print(json.dumps(payload, indent=2, default=str))


def _mock_visual_deps() -> None:
    from shared import rekognition_client

    def fake_rekognition(image_bytes: bytes, claim_id: str = "") -> Dict[str, Any]:
        return rekognition_client.unavailable("demo_mock: Rekognition not invoked")

    rekognition_client.analyze_image_bytes = fake_rekognition  # type: ignore[method-assign]

    from shared import bedrock_client

    def fake_images(*_args: Any, **_kwargs: Any) -> Dict[str, Any]:
        return {
            "findings": [
                {
                    "category": "QUALITY",
                    "severity": "LOW",
                    "description": "Demo mock visual observation: product-like object visible",
                    "evidence": "This finding is from a TEST DOUBLE, not Bedrock",
                    "source": "bedrock",
                }
            ],
            "cross_image_findings": [],
            "limitations": ["DEMO_MOCKED: Bedrock vision was not called"],
            "explanation": "DEMO MOCK explanation. This is not a real Bedrock result.",
        }

    bedrock_client.analyze_images = fake_images  # type: ignore[method-assign]

    from shared import hive_client
    from agent_visual import handler as visual

    hive_client.moderate_visual = lambda *_a, **_k: hive_client.unavailable("demo_mock")  # type: ignore[method-assign]
    visual.check_with_hive = lambda *_a, **_k: hive_client.unavailable("demo_mock")  # type: ignore[assignment]


def _mock_claim_deps() -> None:
    from shared import bedrock_client, vector_store

    def fake_embed(_text: str) -> List[float]:
        raise RuntimeError("demo_mock: Titan embeddings not invoked")

    def fake_text(*_args: Any, **_kwargs: Any) -> Dict[str, Any]:
        return {
            "findings": [
                {
                    "category": "URGENCY",
                    "severity": "LOW",
                    "description": "Demo mock: claim uses time-sensitive language",
                    "evidence": "This finding is from a TEST DOUBLE, not Bedrock",
                    "source": "bedrock",
                }
            ],
            "limitations": ["DEMO_MOCKED: Bedrock text was not called"],
            "explanation": "DEMO MOCK explanation. This is not a real Bedrock result.",
        }

    bedrock_client.analyze_text = fake_text  # type: ignore[method-assign]
    bedrock_client.embed_text = fake_embed  # type: ignore[method-assign]
    vector_store.reset_caches()


def main() -> int:
    parser = argparse.ArgumentParser(description="Aegis Swarm Agent 1 + Agent 2 + Agent 6 demo")
    parser.add_argument(
        "--real-aws",
        action="store_true",
        help="Require real AWS calls; fail instead of using labeled test doubles",
    )
    args = parser.parse_args()
    _load_dotenv()
    os.environ.setdefault("EVIDENCE_BUCKET", "local-demo-bucket")
    os.environ.setdefault("EVIDENCE_KEY_PREFIX", "uploads/")

    aws = _probe_aws()
    print("AWS probe")
    print(json.dumps(aws, indent=2))
    if args.real_aws and not aws["credentials"]:
        print("\n--real-aws was set but no AWS credentials were found.")
        print("Configure the standard AWS credential chain, then retry.")
        return 2

    use_mocks = not aws["credentials"]
    if use_mocks:
        print(
            "\nAWS credentials were NOT found. Continuing with EXPLICIT TEST DOUBLES.\n"
            "Any analysis below is labeled DEMO_MOCKED and is not a real AWS result.\n"
            "Rekognition, Bedrock, Titan, and OpenSearch were not called."
        )
        _mock_visual_deps()
        _mock_claim_deps()
    else:
        print(
            "\nAWS credentials were found. This run will invoke real AWS APIs:\n"
            "  - Amazon Rekognition (DetectLabels/Text/Moderation/Faces)\n"
            "  - Amazon Bedrock Converse (Nova Pro vision + text + Agent 6 explanation)\n"
            "  - Amazon Titan embeddings\n"
            "  - OpenSearch only if OPENSEARCH_ENDPOINT is set\n"
            "Failures will be reported as limitations or agent errors, not faked."
        )
        if not aws["opensearch_endpoint"]:
            print(
                "OPENSEARCH_ENDPOINT is empty -> Agent 2 uses in-memory cosine similarity "
                "(degraded mode, still real embeddings if Titan works)."
            )

    from agent_claim.handler import lambda_handler as claim_handler
    from agent_visual.handler import lambda_handler as visual_handler

    with tempfile.TemporaryDirectory() as workspace:
        photo = os.path.join(workspace, "product.jpg")
        duplicate = os.path.join(workspace, "product-copy.jpg")
        other = os.path.join(workspace, "other.jpg")
        _make_image(photo, (40, 80, 160), with_exif=True, stripe=120)
        _make_image(duplicate, (40, 80, 160), with_exif=True, stripe=120)
        _make_image(other, (200, 30, 30), with_exif=False, stripe=300)

        visual_event = {
            "claim_id": "DEMO-001",
            "product_category": "electronics",
            "customer_claimed_condition": "Screen arrived cracked",
            "local_image_paths": [photo, duplicate, other],
        }
        claim_event = {
            "claim_id": "DEMO-001",
            "product_category": "electronics",
            "order_value_usd": 249.99,
            "customer_claimed_condition": "Screen arrived cracked",
            "customer_text": (
                "The box was completely empty when it arrived and the screen is shattered. "
                "I need a refund today or my lawyer will be in touch."
            ),
        }
        with ThreadPoolExecutor(max_workers=2) as pool:
            visual_future = pool.submit(visual_handler, visual_event, None)
            claim_future = pool.submit(claim_handler, claim_event, None)
            visual = visual_future.result()
            claim = claim_future.result()
        _print_result("Agent 1 - Visual Evidence", visual)
        _print_result("Agent 3 - Claim Intelligence (Agent 2 in this repo)", claim)

        from pipeline import combine_agents

        agent6 = combine_agents(visual, claim, claim_id="DEMO-001", use_bedrock=not use_mocks)
        _print_result("Agent 6 - Final decision", agent6)

    print("\nHow to read this output")
    print("- Agent 1 and Agent 3 run in parallel; Agent 6 decides after both finish.")
    print("- tool_status / limitations tell you which AWS services actually ran.")
    print("- retrieved_patterns are application-retrieved, not invented by the LLM.")
    print("- Agent 6 decision is FRAUD, NOT_FRAUD, or HUMAN_REVIEW.")
    print("- Auto-decide only when confidence >= 0.80; otherwise DynamoDB human review.")
    print("- recommendation is the legacy advisory approve|review|escalate label.")
    if use_mocks:
        print("- This run used TEST DOUBLES. Do not treat it as a real AWS demo.")
        return 0
    visual_ok = visual.get("status") == "ok"
    claim_ok = claim.get("status") == "ok"
    agent6_ok = isinstance(agent6, dict) and agent6.get("agent") == "agent-6-orchestrator"
    return 0 if visual_ok and claim_ok and agent6_ok else 1


if __name__ == "__main__":
    sys.exit(main())
