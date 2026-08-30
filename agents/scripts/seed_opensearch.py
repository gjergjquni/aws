"""Seed bundled synthetic fraud-pattern documents into OpenSearch.

Requires OPENSEARCH_ENDPOINT, AWS credentials, and Bedrock Titan embedding access.
Does nothing silent: prints each step and exits non-zero on failure.

Usage (from repo root, with src on PYTHONPATH):

    set PYTHONPATH=src
    python scripts/seed_opensearch.py
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load_dotenv(path: str) -> None:
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def main() -> int:
    _load_dotenv(os.path.join(ROOT, ".env"))
    from shared import bedrock_client, config, vector_store

    endpoint = config.opensearch_endpoint()
    if not endpoint:
        print("OPENSEARCH_ENDPOINT is not set. Refusing to pretend the index was seeded.")
        print("Set it to a real OpenSearch or OpenSearch Serverless endpoint first.")
        return 2

    index = config.opensearch_index()
    dimensions = config.embedding_dimensions()
    documents = vector_store.load_documents()
    print(f"Endpoint: {endpoint}")
    print(f"Index: {index}")
    print(f"Documents: {len(documents)}")
    print(f"Embedding model: {config.embedding_model_id()} dim={dimensions}")

    from opensearchpy import OpenSearch, RequestsHttpConnection
    from requests_aws4auth import AWS4Auth
    import boto3

    session = boto3.Session()
    credentials = session.get_credentials()
    if credentials is None:
        print("No AWS credentials available for SigV4.")
        return 2
    frozen = credentials.get_frozen_credentials()
    host = endpoint.replace("https://", "").replace("http://", "")
    service = "aoss" if "aoss" in host else "es"
    auth = AWS4Auth(
        frozen.access_key, frozen.secret_key, config.aws_region(), service, session_token=frozen.token
    )
    client = OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=30,
    )

    mapping = {
        "settings": {"index": {"knn": True}},
        "mappings": {
            "properties": {
                "pattern_id": {"type": "keyword"},
                "pattern_type": {"type": "keyword"},
                "description": {"type": "text"},
                "example_claim": {"type": "text"},
                "source_type": {"type": "keyword"},
                "source_reference": {"type": "keyword"},
                "created_at": {"type": "date"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": dimensions,
                    "method": {"name": "hnsw", "space_type": "cosinesimil", "engine": "nmslib"},
                },
            }
        },
    }
    if not client.indices.exists(index=index):
        client.indices.create(index=index, body=mapping)
        print(f"Created index {index}")
    else:
        print(f"Index {index} already exists")

    for document in documents:
        text = vector_store._document_text(document)
        vector = bedrock_client.embed_text(text)
        body = {**document, "embedding": vector}
        client.index(index=index, id=document["pattern_id"], body=body)
        print(f"Indexed {document['pattern_id']} ({len(vector)} dims)")

    client.indices.refresh(index=index)
    print("Seed complete. These are real OpenSearch documents, not simulated hits.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
