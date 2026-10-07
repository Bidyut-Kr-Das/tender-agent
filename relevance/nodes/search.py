import logging
from typing import Any

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
        try:
            total = qdrant.count(collection_name=coll, exact=True).count
            logger.info("relevance collection=%s total_points=%s", coll, total)
        except Exception as ce:
            logger.warning("relevance count failed collection=%s error=%s", coll, ce)
        res = qdrant.query_points(
            collection_name=coll,
            query=dense,
            using="dense",
            limit=3,
            with_payload=True,
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
        logger.info(
            "relevance search ref=%s collection=%s query=%r hits=%s",
            ref, coll, query[:120], len(hits),
        )
        for i, h in enumerate(hits):
            logger.info(
                "relevance hit #%s ref=%s score=%.4f id=%s text=%r",
                i, ref, h.get("score", 0.0), h.get("id"), (h.get("text") or "")[:300],
            )
        if not hits:
            logger.warning("relevance search returned 0 feedback chunks ref=%s collection=%s", ref, coll)
        return {"hits": hits, "status": "searched", "error": None}
    except Exception as e:
        err = f"qdrant query failed: {type(e).__name__}: {e}"
        logger.error(err, exc_info=True)
        return {"hits": [], "status": "failed", "error": err}