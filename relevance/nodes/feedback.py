import logging
import uuid
from typing import Any

from qdrant_client.http.models import PointStruct

from core.config import settings
from database.connection import get_session_context
from database.models import Feedback
from vector.embeddings import get_dense
from vector.qdrant import ensure_collection, qdrant

logger = logging.getLogger(__name__)


def embed_feedback(state: dict[str, Any]) -> dict[str, Any]:
    ref = state.get("reference_no") or ""
    extra = state.get("extra") or {}
    chunk = "\n".join(f"{k}: {v}" for k, v in extra.items())
    if not chunk.strip():
        err = "extra empty, nothing to embed"
        logger.error("%s ref=%s", err, ref)
        return {"status": "failed", "error": err, "chunk": ""}

    # ponytail: dense only — feedback chunk is one short text, BM25 adds nothing
    try:
        vec = get_dense().embed_documents([chunk])[0]
    except Exception as e:
        err = f"embedding failed: {type(e).__name__}: {e}"
        logger.error(err, exc_info=True)
        return {"status": "failed", "error": err, "chunk": chunk}

    # stable id per ref+company+content, dedupes redelivered messages
    point_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"feedback:{ref}:{state.get('company')}:{chunk}")

    try:
        coll = ensure_collection(name=settings.relevance_collection)
        qdrant.upsert(
            collection_name=coll,
            points=[
                PointStruct(
                    id=str(point_id),
                    vector={"dense": vec},
                    payload={
                        "reference_no": ref,
                        "referenceNo": ref,
                        "company": state.get("company"),
                        "payload_type": "feedback",
                        "text": chunk,
                    },
                )
            ],
            wait=True,
        )
        logger.info("feedback upserted ref=%s collection=%s point=%s", ref, coll, point_id)
    except Exception as e:
        err = f"qdrant upsert failed: {type(e).__name__}: {e}"
        logger.error(err, exc_info=True)
        return {"status": "failed", "error": err, "chunk": chunk, "vector_ids": []}

    try:
        with get_session_context() as session:
            session.add(Feedback(reference_no=ref, company=state.get("company"), user_feedback=chunk))
            session.commit()
        logger.info("feedback row saved ref=%s", ref)
    except Exception as e:
        err = f"feedback db save failed: {type(e).__name__}: {e}"
        logger.error(err, exc_info=True)
        # ponytail: vector already pushed, row missing — nack so message retried, dedupe id makes it safe
        return {"status": "failed", "error": err, "chunk": chunk, "vector_ids": [str(point_id)]}

    return {"chunk": chunk, "vector_ids": [str(point_id)], "status": "indexed", "error": None}