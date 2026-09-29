import logging
from typing import Any

from qdrant_client.http.models import FieldCondition, Filter, MatchValue

from core.config import settings
from vector.embeddings import get_dense
from vector.qdrant import ensure_collection, qdrant

logger = logging.getLogger(__name__)


def search(state: dict[str, Any]) -> dict[str, Any]:
    query = (state.get("query") or "").strip()
    ref = (state.get("reference_no") or "").strip()

    if not query:
        err = "query required (run generate_query first)"
        logger.error("%s ref=%s", err, ref)
        return {"hits": [], "status": "failed", "error": err}

    try:
        dense = get_dense().embed_query(query)
    except Exception as e:
        err = f"dense embed failed: {type(e).__name__}: {e}"
        logger.error(err, exc_info=True)
        return {"hits": [], "status": "failed", "error": err}

    try:
        coll = ensure_collection(name=settings.relevance_collection)
        res = qdrant.query_points(
            collection_name=coll,
            query=dense,
            using="dense",
            limit=3,
            with_payload=True,
            query_filter=Filter(must=[FieldCondition(key="reference_no", match=MatchValue(value=ref))]),
        )
        points = res.points if hasattr(res, "points") else []
        hits = []
        for p in points:
            payload = getattr(p, "payload", {}) or {}
            hits.append(
                {
                    "id": str(getattr(p, "id", "")),
                    "score": float(getattr(p, "score", 0) or 0),
                    "text": payload.get("text") or "",
                    "payload": payload,
                }
            )
        logger.info("relevance search ref=%s query=%r hits=%s", ref, query[:80], len(hits))
        return {"hits": hits, "status": "searched", "error": None}
    except Exception as e:
        err = f"qdrant query failed: {type(e).__name__}: {e}"
        logger.error(err, exc_info=True)
        return {"hits": [], "status": "failed", "error": err}