"""Unit test for the unified xiaohongshu keyword-generation prompt.

After the prompt-input unification, xhs keyword generation feeds the same
``build_profile_summary`` dict every other discovery prompt sees (B站 / YouTube /
X query-gen, all-platform evaluation) instead of the old top-15
``name | category | weight`` tuple list.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from openbiliclaw.llm.base import LLMResponse
from openbiliclaw.soul.profile import InterestTag, PreferenceLayer, SoulProfile
from openbiliclaw.sources.xhs_keyword_gen import generate_xhs_keywords


@dataclass
class _RecordingLLM:
    payload: str
    calls: list[dict[str, object]] = field(default_factory=list)

    async def complete_structured_task(
        self,
        *,
        system_instruction: str,
        user_input: str,
        history: list[dict[str, str]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        caller: str = "",
        reasoning_effort: str | None = None,
    ) -> object:
        self.calls.append({"user_input": user_input, "caller": caller})
        return LLMResponse(content=self.payload, provider="test", model="test-model")


async def test_xhs_keyword_prompt_uses_unified_profile_summary() -> None:
    profile = SoulProfile(
        preferences=PreferenceLayer(
            interests=[InterestTag(name="露营", category="生活", weight=0.9)],
            disliked_topics=["标题党"],
        )
    )
    llm = _RecordingLLM('{"keywords": ["露营 装备 推荐"]}')

    keywords = await generate_xhs_keywords(llm, profile, count=3)  # type: ignore[arg-type]

    assert keywords == ["露营 装备 推荐"]
    assert llm.calls[0]["caller"] == "sources.xhs.keyword_gen"
    user_input = str(llm.calls[0]["user_input"])
    assert "<profile_summary>" in user_input
    # interest_domains + disliked_topics are structured fields the old tuple
    # prompt never carried — their presence proves the unified dict is in use.
    assert "interest_domains" in user_input
    assert "标题党" in user_input
    assert "name | category | weight" not in user_input
