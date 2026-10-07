import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class Category(str, Enum):
    power_transmission = "power_transmission"
    power_distribution = "power_distribution"
    water_distribution = "water_distribution"


# node runs only when the incoming category is one of these, and outputs one of these
GATED = frozenset(c.value for c in Category)

SYSTEM_PROMPT = """You classify a tender brief into EXACTLY ONE category. Use only the allowed values below; never invent another value.

Allowed values (choose exactly one):
- power_transmission
- power_distribution
- water_distribution

Apply the rules in order; the first match wins.

1. Return power_transmission when:
- the brief contains the word "opgw" AND does NOT contain the word "supply"
- the brief contains the word "transmission"
- the brief mentions a substation at a voltage ABOVE 33 kV

2. Return power_distribution when:
- the brief contains the word "distribution"
- the brief contains both "under" and "ground"
- the brief mentions a substation at 33 kV OR BELOW

Voltage rule: above 33 kV maps to power_transmission; 33 kV and below maps to power_distribution. In a paired rating such as "132/33 kV" the substation counts as its HIGHER voltage (132 kV -> power_transmission).

If no rule matches, return the incoming category value unchanged; if the incoming category is empty, return null.

Respond with one of: power_transmission, power_distribution, water_distribution."""


class CategoryVerdict(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: Category | None = Field(default=None, description="the single matching category, or null when the incoming category is empty and no rule matches")


def categorise(state: dict[str, Any]) -> dict[str, Any]:
    extra = state.get("extra") or {}
    incoming = str(extra.get("category") or "").strip().lower()

    brief = extra.get("tenderbrief") or extra.get("tenderBrief") or ""
    try:
        from intelligence.llm import get_llm

        llm = get_llm()
        structured = llm.with_structured_output(CategoryVerdict)
        result = structured.invoke(
            [
                ("system", SYSTEM_PROMPT),
                ("human", f"incoming category: {incoming}\n\nbrief: {brief}"),
            ]
        )
        if not result:
            raise ValueError("empty structured output")
        decided = result.category.value if result.category else incoming
    except Exception as e:
        logger.error("categorise failed incoming=%s error=%s, keeping incoming", incoming, e, exc_info=True)
        return {"category": incoming} if incoming else {}

    if not decided:
        return {}  # empty incoming and no rule matched: pass through unchanged
    logger.info("categorise incoming=%s decided=%s", incoming, decided)
    return {"category": decided}


if __name__ == "__main__":
    assert GATED == {"power_transmission", "power_distribution", "water_distribution"}, GATED
    for value in GATED:
        assert value in SYSTEM_PROMPT, value
    assert "opgw" in SYSTEM_PROMPT and "33 kV" in SYSTEM_PROMPT
    print("category agent prompt ok")
