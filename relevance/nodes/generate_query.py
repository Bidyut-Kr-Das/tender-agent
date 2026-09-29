import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from intelligence.llm import get_llm

logger = logging.getLogger(__name__)


class RelevanceQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query: str = Field(description="single search query over stored feedback chunks")


def generate_query(state: dict[str, Any]) -> dict[str, Any]:
    ref = (state.get("reference_no") or "").strip()
    extra = state.get("extra") or {}
    brief = (extra.get("tenderbrief") or extra.get("tenderBrief") or "").strip()
    itemcategory = (extra.get("itemcategory") or extra.get("itemCategory") or "").strip()

    if not brief:
        err = "tenderbrief missing in extra"
        logger.error("%s ref=%s", err, ref)
        return {"query": "", "status": "failed", "error": err}

    try:
        llm = get_llm()
        structured = llm.with_structured_output(RelevanceQuery)
        result = structured.invoke(
            [
                ("system", "You build a short similarity-search query over tender feedback chunks. Query must capture the brief's subject and the item category. One plain string, no preamble."),
                ("human", f"brief: {brief}\nitem category: {itemcategory or 'unspecified'}"),
            ]
        )
        query = (result.query or "").strip() if result else ""
        if not query:
            logger.warning("generate_query empty ref=%s", ref)
            return {"query": "", "status": "failed", "error": "empty query"}
        logger.info("generate_query ref=%s query=%r", ref, query)
        return {"query": query, "status": "planned", "error": None}
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        logger.error("generate_query failed ref=%s error=%s", ref, err, exc_info=True)
        return {"query": "", "status": "failed", "error": err}