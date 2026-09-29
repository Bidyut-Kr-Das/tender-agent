import json
import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from database.connection import get_session_context
from database.models import AIRelevance
from intelligence.llm import get_llm
from relevance.prompts import DEFAULT, PROMPTS
from relevance.prompts import DEFAULT, PROMPTS

logger = logging.getLogger(__name__)


class RelevanceVerdict(BaseModel):
    model_config = ConfigDict(extra="ignore")

    valid: bool = Field(description="whether the brief is a valid tender fit for the company")
    reason: str = Field(description="why the brief is or is not valid, grounded in the feedback chunks")


def analyze(state: dict[str, Any]) -> dict[str, Any]:
    ref = (state.get("reference_no") or "").strip()
    extra = state.get("extra") or {}
    brief = (extra.get("tenderbrief") or extra.get("tenderBrief") or "").strip()
    itemcategory = (extra.get("itemcategory") or extra.get("itemCategory") or "").strip()
    hits = state.get("hits") or []

    if not brief:
        err = "tenderbrief missing in extra"
        logger.error("%s ref=%s", err, ref)
        return {"verdict": {}, "status": "failed", "error": err}

    feedback_text = "\n\n".join(
        f"[score {h.get('score', 0):.3f}]\n{h.get('text') or ''}" for h in hits if h.get("text")
    ) or "(no feedback chunks found)"

    company = str(state.get("company") or "").lower()
    system_prompt = (PROMPTS.get(company) or DEFAULT).strip()
    if not system_prompt:
        logger.warning("prompt blank for company=%s, falling back to default", company)
        system_prompt = DEFAULT

    try:
        llm = get_llm()
        structured = llm.with_structured_output(RelevanceVerdict)
        result = structured.invoke(
            [
                ("system", system_prompt),
("human", f"item category: {itemcategory or 'unspecified'}\nbrief: {brief}\n\nprior feedback:\n{feedback_text}"),
            ]
        )
        if not result:
            raise ValueError("empty structured output")
        verdict = {"valid": result.valid, "reason": result.reason}
        logger.info("analyze ref=%s valid=%s", ref, result.valid)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        logger.error("analyze failed ref=%s error=%s", ref, err, exc_info=True)
        return {"verdict": {}, "status": "failed", "error": err}

    # persist — ponytail: row stores verdict json + reason; a db failure fails the job (analysis is the point)
    try:
        with get_session_context() as session:
            session.add(
                AIRelevance(
                    reference_no=ref,
                    company=state.get("company"),
                    brief=brief,
                    ai_answer=json.dumps(verdict),
                    ai_reason=result.reason,
                )
            )
            session.commit()
        logger.info("ai_relevance row saved ref=%s", ref)
    except Exception as e:
        err = f"ai_relevance db save failed: {type(e).__name__}: {e}"
        logger.error(err, exc_info=True)
        return {"verdict": verdict, "status": "failed", "error": err}

    return {"verdict": verdict, "status": "analyzed", "error": None}