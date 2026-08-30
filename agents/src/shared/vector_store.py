"""Vector retrieval for Agent 2 (claim intelligence).

Modes, in order of preference:

1. OPENSEARCH — when OPENSEARCH_ENDPOINT is set. Real k-NN query. Failures are
   explicit; results are never invented.
2. IN_MEMORY — Titan embeddings + cosine similarity over bundled synthetic
   documents. Same algorithm, no hosted cluster. Documented as degraded.
3. LEXICAL — token overlap when embeddings cannot be generated. Explicitly not
   semantic search.

The LLM never produces retrieval hits. Application code retrieves, then the
model is shown the hits as TOOL FACTS.
"""

from __future__ import annotations

import json
import math
import os
import re
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from . import bedrock_client, config, observability, schemas
from .errors import BedrockInvocationError, RetryableAgentError

logger = config.get_logger(__name__)

_TOKEN = re.compile(r"[a-z0-9]+")

_documents_cache: Optional[List[Dict[str, Any]]] = None
_memory_vectors: Optional[List[Tuple[Dict[str, Any], List[float]]]] = None

EmbedFn = Callable[[str], List[float]]


def _documents_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config",
        config.FRAUD_PATTERN_DOCUMENTS_FILENAME,
    )


def load_documents() -> List[Dict[str, Any]]:
    global _documents_cache
    if _documents_cache is not None:
        return _documents_cache
    path = _documents_path()
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        payload = payload.get("documents") or payload.get("patterns") or []
    if not isinstance(payload, list) or not payload:
        raise ValueError("fraud pattern documents file is empty")
    _documents_cache = [item for item in payload if isinstance(item, dict) and item.get("pattern_id")]
    logger.info("Loaded %d fraud-pattern documents", len(_documents_cache))
    return _documents_cache


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for a, b in zip(left, right):
        dot += a * b
        left_norm += a * a
        right_norm += b * b
    if left_norm <= 0.0 or right_norm <= 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / math.sqrt(left_norm * right_norm)))


def _document_text(document: Dict[str, Any]) -> str:
    parts = [
        str(document.get("pattern_id") or ""),
        str(document.get("pattern_type") or ""),
        str(document.get("description") or ""),
        str(document.get("example_claim") or ""),
    ]
    return "\n".join(part for part in parts if part)


def _tokens(text: str) -> set[str]:
    return {token for token in _TOKEN.findall(text.lower()) if len(token) > 2}


def lexical_score(query: str, document: Dict[str, Any]) -> float:
    query_tokens = _tokens(query)
    doc_tokens = _tokens(_document_text(document))
    if not query_tokens or not doc_tokens:
        return 0.0
    overlap = query_tokens & doc_tokens
    return len(overlap) / math.sqrt(len(query_tokens) * len(doc_tokens))


def _embed_default(text: str) -> List[float]:
    return bedrock_client.embed_text(text)


def _ensure_memory_index(embed: EmbedFn) -> List[Tuple[Dict[str, Any], List[float]]]:
    global _memory_vectors
    if _memory_vectors is not None:
        return _memory_vectors
    indexed: List[Tuple[Dict[str, Any], List[float]]] = []
    for document in load_documents():
        vector = embed(_document_text(document))
        indexed.append((document, vector))
    _memory_vectors = indexed
    logger.info("Built in-memory vector index with %d documents", len(indexed))
    return indexed


def reset_caches() -> None:
    """Test helper."""
    global _documents_cache, _memory_vectors
    _documents_cache = None
    _memory_vectors = None


def search_opensearch(query_vector: List[float], *, k: int = 5) -> List[Dict[str, Any]]:
    endpoint = config.opensearch_endpoint()
    index = config.opensearch_index()
    try:
        from opensearchpy import OpenSearch, RequestsHttpConnection
        from opensearchpy.exceptions import OpenSearchException
        from requests_aws4auth import AWS4Auth
        import boto3
    except ImportError as exc:
        raise RuntimeError("opensearch-py is not installed") from exc

    session = boto3.Session()
    credentials = session.get_credentials()
    if credentials is None:
        raise RuntimeError("No AWS credentials available for OpenSearch SigV4")
    frozen = credentials.get_frozen_credentials()
    region = config.aws_region()
    host = endpoint.replace("https://", "").replace("http://", "")
    service = "aoss" if "aoss" in host else "es"
    auth = AWS4Auth(
        frozen.access_key, frozen.secret_key, region, service, session_token=frozen.token
    )
    client = OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=15,
    )
    body = {
        "size": k,
        "query": {
            "knn": {
                "embedding": {
                    "vector": query_vector,
                    "k": k,
                }
            }
        },
    }
    try:
        response = client.search(index=index, body=body)
    except OpenSearchException as exc:
        observability.aws_failure(
            logger, service="opensearch", operation="search", error=str(exc)
        )
        raise
    hits = []
    for hit in (response.get("hits") or {}).get("hits") or []:
        source = hit.get("_source") or {}
        score = float(hit.get("_score") or 0.0)
        # nmslib/faiss cosine scores are typically in 0-1 or 0-2 depending on engine.
        similarity = score if 0.0 <= score <= 1.0 else max(0.0, min(1.0, score / 2.0))
        hits.append(
            schemas.retrieved_pattern(
                pattern_id=str(source.get("pattern_id") or hit.get("_id") or ""),
                similarity_score=similarity,
                description=str(source.get("description") or ""),
                source="opensearch",
                extra={
                    "pattern_type": source.get("pattern_type"),
                    "example_claim": source.get("example_claim"),
                    "source_type": source.get("source_type"),
                    "source_reference": source.get("source_reference"),
                },
            )
        )
    return hits


def search_in_memory(query_vector: List[float], *, k: int = 5, embed: Optional[EmbedFn] = None) -> List[Dict[str, Any]]:
    indexed = _ensure_memory_index(embed or _embed_default)
    ranked = sorted(
        ((cosine_similarity(query_vector, vector), document) for document, vector in indexed),
        key=lambda item: item[0],
        reverse=True,
    )
    hits = []
    for similarity, document in ranked[:k]:
        hits.append(
            schemas.retrieved_pattern(
                pattern_id=str(document.get("pattern_id") or ""),
                similarity_score=similarity,
                description=str(document.get("description") or ""),
                source="in_memory_vector",
                extra={
                    "pattern_type": document.get("pattern_type"),
                    "example_claim": document.get("example_claim"),
                    "source_type": document.get("source_type"),
                    "source_reference": document.get("source_reference"),
                },
            )
        )
    return hits


def search_lexical(query: str, *, k: int = 5) -> List[Dict[str, Any]]:
    ranked = sorted(
        ((lexical_score(query, document), document) for document in load_documents()),
        key=lambda item: item[0],
        reverse=True,
    )
    hits = []
    for similarity, document in ranked[:k]:
        hits.append(
            schemas.retrieved_pattern(
                pattern_id=str(document.get("pattern_id") or ""),
                similarity_score=similarity,
                description=str(document.get("description") or ""),
                source="lexical_fallback",
                extra={
                    "pattern_type": document.get("pattern_type"),
                    "example_claim": document.get("example_claim"),
                    "source_type": document.get("source_type"),
                    "source_reference": document.get("source_reference"),
                },
            )
        )
    return hits


def retrieve(query_text: str, *, k: int = 5, embed: Optional[EmbedFn] = None) -> Dict[str, Any]:
    """Return hits plus the retrieval mode actually used.

    Never asks an LLM to invent matches.
    """
    threshold = config.vector_similarity_threshold()
    embed_fn = embed or _embed_default
    query_vector: Optional[List[float]] = None
    embedding_error: Optional[str] = None

    try:
        query_vector = embed_fn(query_text)
    except (BedrockInvocationError, RetryableAgentError, Exception) as exc:
        embedding_error = str(exc)
        observability.aws_failure(
            logger, service="bedrock", operation="embed_text", error=embedding_error
        )

    if query_vector is not None and config.opensearch_endpoint():
        try:
            hits = search_opensearch(query_vector, k=k)
            kept = [hit for hit in hits if hit["similarity_score"] >= threshold]
            return {
                "mode": "OPENSEARCH",
                "hits": kept,
                "limitation": None,
            }
        except Exception as exc:
            logger.warning("OpenSearch search failed; falling back to in-memory: %s", exc)
            # Fall through to in-memory with the same query vector.

    if query_vector is not None:
        try:
            hits = search_in_memory(query_vector, k=k, embed=embed_fn)
            kept = [hit for hit in hits if hit["similarity_score"] >= threshold]
            limitation = None
            mode = "IN_MEMORY"
            if config.opensearch_endpoint():
                limitation = (
                    "OpenSearch query failed; used in-memory cosine similarity over bundled documents"
                )
            else:
                limitation = (
                    "OpenSearch is not configured; used in-memory cosine similarity over bundled documents"
                )
            return {"mode": mode, "hits": kept, "limitation": limitation}
        except Exception as exc:
            logger.warning("In-memory vector search failed; falling back to lexical: %s", exc)
            embedding_error = embedding_error or str(exc)

    hits = search_lexical(query_text, k=k)
    lexical_threshold = min(0.18, threshold)
    kept = [hit for hit in hits if hit["similarity_score"] >= lexical_threshold]
    reason = embedding_error or "embeddings unavailable"
    return {
        "mode": "LEXICAL",
        "hits": kept,
        "limitation": (
            f"Semantic embeddings unavailable ({reason}); used lexical overlap. "
            "This is not vector search."
        ),
    }
