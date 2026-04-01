"""SpeculationEvaluator — multi-dimension scoring of speculative interest quality.

Evaluates speculations across 5 dimensions: plausibility, novelty,
specificity, confirmation rate, and no-hallucination. Supports both
automated (LLM-based) and human-feedback evaluation modes.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openbiliclaw.soul.profile import OnionProfile
    from openbiliclaw.soul.speculator import SpeculativeInterest

logger = logging.getLogger(__name__)

# Dimension weights for overall score
_DIM_WEIGHTS: dict[str, float] = {
    "plausibility": 0.25,
    "novelty": 0.20,
    "specificity": 0.15,
    "confirmation_rate": 0.25,
    "no_hallucination": 0.15,
}

# All dimensions map to the same prompt (only LLM-controlled variable)
SPECULATION_FIELD_TO_PARAM: dict[str, str] = {
    k: "speculation_generation_prompt" for k in _DIM_WEIGHTS
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SpeculationScore:
    """Score for a single speculation."""

    domain: str = ""
    plausibility: float = 0.0
    novelty: float = 0.0
    specificity: float = 0.0
    no_hallucination: float = 0.0
    overall: float = 0.0
    details: str = ""


@dataclass
class SpeculationEvalReport:
    """Complete evaluation report for one speculation generation run."""

    speculation_scores: list[SpeculationScore] = field(default_factory=list)
    confirmation_rate: float = 0.0
    mean_plausibility: float = 0.0
    mean_novelty: float = 0.0
    mean_specificity: float = 0.0
    mean_no_hallucination: float = 0.0
    overall_score: float = 0.0
    worst_dimensions: list[dict[str, Any]] = field(default_factory=list)
    attributions: list[str] = field(default_factory=list)
    persona_id: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "overall_score": self.overall_score,
            "confirmation_rate": self.confirmation_rate,
            "mean_plausibility": self.mean_plausibility,
            "mean_novelty": self.mean_novelty,
            "mean_specificity": self.mean_specificity,
            "mean_no_hallucination": self.mean_no_hallucination,
            "speculation_scores": [
                {
                    "domain": s.domain,
                    "plausibility": s.plausibility,
                    "novelty": s.novelty,
                    "specificity": s.specificity,
                    "no_hallucination": s.no_hallucination,
                    "overall": s.overall,
                    "details": s.details,
                }
                for s in self.speculation_scores
            ],
            "worst_dimensions": self.worst_dimensions,
            "attributions": self.attributions,
            "persona_id": self.persona_id,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------


def _no_hallucination_score(
    domain: str,
    confirmed_domains: list[str],
) -> float:
    """Check if speculation restates an existing confirmed interest. 0.0 = hallucination."""
    domain_lower = domain.lower()
    for confirmed in confirmed_domains:
        confirmed_lower = confirmed.lower()
        if domain_lower in confirmed_lower or confirmed_lower in domain_lower:
            return 0.0
    # Token overlap check
    from openbiliclaw.soul.speculator import _tokenize

    domain_tokens = _tokenize(domain)
    for confirmed in confirmed_domains:
        conf_tokens = _tokenize(confirmed)
        if domain_tokens and conf_tokens:
            overlap = len(domain_tokens & conf_tokens) / len(domain_tokens)
            if overlap >= 0.6:
                return 0.2
    return 1.0


def _confirmation_rate_score(rate: float) -> float:
    """Score confirmation rate. Target is 0.3-0.7; penalize both extremes."""
    return max(0.0, 1.0 - 2.0 * abs(rate - 0.5))


async def _llm_eval_speculation(
    spec_domain: str,
    spec_reason: str,
    profile_context: str,
) -> dict[str, float]:
    """Use LLM to score plausibility, novelty, and specificity."""
    try:
        from openbiliclaw.eval.agents import collect_json

        from claude_agent_sdk import ClaudeAgentOptions

        result = await collect_json(
            prompt=(
                f"评估以下推测兴趣的质量。\n\n"
                f"用户画像:\n{profile_context[:1000]}\n\n"
                f"推测方向: {spec_domain}\n"
                f"推理依据: {spec_reason}\n\n"
                f"请从三个维度评分 (0-1):\n"
                f"1. plausibility: 心理桥接推理是否合理？能否从已有兴趣自然推导出来？\n"
                f"2. novelty: 是否真正跨域？(0.1=已有兴趣的简单延伸, 0.9=创造性的交叉推理)\n"
                f"3. specificity: 能否在B站搜到这类内容？(0.1=太抽象, 0.9=可直接搜索)\n\n"
                f'返回 JSON: {{"plausibility": 0.0, "novelty": 0.0, "specificity": 0.0, '
                f'"reasoning": "简要说明"}}'
            ),
            options=ClaudeAgentOptions(
                system_prompt=(
                    "你是推测兴趣质量评估器。客观评分：完全合理=0.8+，"
                    "部分合理=0.5-0.7，不合理=0-0.4。只返回 JSON。"
                ),
                max_turns=1,
            ),
            max_retries=1,
        )
        return {
            "plausibility": max(0.0, min(1.0, float(result.get("plausibility", 0.5)))),
            "novelty": max(0.0, min(1.0, float(result.get("novelty", 0.5)))),
            "specificity": max(0.0, min(1.0, float(result.get("specificity", 0.5)))),
        }
    except Exception:
        logger.warning("LLM eval failed for %s, using defaults", spec_domain)
        return {"plausibility": 0.5, "novelty": 0.5, "specificity": 0.5}


# ---------------------------------------------------------------------------
# SpeculationEvaluator
# ---------------------------------------------------------------------------


class SpeculationEvaluator:
    """Evaluate speculative interest generation quality."""

    def __init__(self, *, dim_weights: dict[str, float] | None = None) -> None:
        self._weights = dim_weights or dict(_DIM_WEIGHTS)

    async def evaluate(
        self,
        speculations: list[SpeculativeInterest],
        profile: OnionProfile,
        confirmation_results: dict[str, bool] | None = None,
    ) -> SpeculationEvalReport:
        """Full automated evaluation of speculations against a profile."""
        if not speculations:
            return SpeculationEvalReport(timestamp=datetime.now().isoformat())

        # Collect confirmed interest domains for hallucination check
        confirmed_domains = [d.domain for d in profile.interest.likes]
        profile_ctx = profile.to_llm_context()

        scores: list[SpeculationScore] = []
        for spec in speculations:
            # LLM scoring for plausibility/novelty/specificity
            llm_scores = await _llm_eval_speculation(
                spec.domain, spec.reason, profile_ctx,
            )
            # Algorithmic no-hallucination check
            nh = _no_hallucination_score(spec.domain, confirmed_domains)

            per_spec_overall = (
                llm_scores["plausibility"] * 0.35
                + llm_scores["novelty"] * 0.30
                + llm_scores["specificity"] * 0.20
                + nh * 0.15
            )
            scores.append(SpeculationScore(
                domain=spec.domain,
                plausibility=llm_scores["plausibility"],
                novelty=llm_scores["novelty"],
                specificity=llm_scores["specificity"],
                no_hallucination=nh,
                overall=round(per_spec_overall, 4),
            ))

        # Confirmation rate
        conf_rate = 0.5  # default if no simulation data
        if confirmation_results:
            total = len(confirmation_results)
            promoted = sum(1 for v in confirmation_results.values() if v)
            conf_rate = promoted / total if total > 0 else 0.5
        conf_rate_score = _confirmation_rate_score(conf_rate)

        # Means
        n = len(scores)
        mean_p = sum(s.plausibility for s in scores) / n
        mean_n = sum(s.novelty for s in scores) / n
        mean_s = sum(s.specificity for s in scores) / n
        mean_nh = sum(s.no_hallucination for s in scores) / n

        overall = (
            self._weights["plausibility"] * mean_p
            + self._weights["novelty"] * mean_n
            + self._weights["specificity"] * mean_s
            + self._weights["confirmation_rate"] * conf_rate_score
            + self._weights["no_hallucination"] * mean_nh
        )

        # Worst dimensions
        dims = [
            {"dimension": "plausibility", "score": mean_p},
            {"dimension": "novelty", "score": mean_n},
            {"dimension": "specificity", "score": mean_s},
            {"dimension": "confirmation_rate", "score": conf_rate_score},
            {"dimension": "no_hallucination", "score": mean_nh},
        ]
        worst = sorted(dims, key=lambda d: d["score"])[:3]

        attributions = [
            f"{d['dimension']} ({d['score']:.2f}) → speculation_generation_prompt"
            for d in worst if d["score"] < 0.7
        ]

        return SpeculationEvalReport(
            speculation_scores=scores,
            confirmation_rate=round(conf_rate, 4),
            mean_plausibility=round(mean_p, 4),
            mean_novelty=round(mean_n, 4),
            mean_specificity=round(mean_s, 4),
            mean_no_hallucination=round(mean_nh, 4),
            overall_score=round(overall, 4),
            worst_dimensions=worst,
            attributions=attributions,
            timestamp=datetime.now().isoformat(),
        )

    async def evaluate_with_human(
        self,
        speculations: list[SpeculativeInterest],
        human_feedback: dict[str, dict[str, float]],
    ) -> SpeculationEvalReport:
        """Build report from human per-speculation feedback.

        human_feedback format:
        {
            "博弈论科普": {"plausibility": 0.8, "novelty": 0.6, "specificity": 0.9},
            ...
        }
        """
        scores: list[SpeculationScore] = []
        for spec in speculations:
            fb = human_feedback.get(spec.domain, {})
            if not isinstance(fb, dict):
                continue
            p = float(fb.get("plausibility", 0.5))
            n = float(fb.get("novelty", 0.5))
            s = float(fb.get("specificity", 0.5))
            per_overall = p * 0.4 + n * 0.3 + s * 0.3
            scores.append(SpeculationScore(
                domain=spec.domain,
                plausibility=p,
                novelty=n,
                specificity=s,
                no_hallucination=1.0,  # human review assumed no hallucination
                overall=round(per_overall, 4),
                details=str(fb.get("note", "")),
            ))

        if not scores:
            return SpeculationEvalReport(timestamp=datetime.now().isoformat())

        count = len(scores)
        mean_p = sum(s.plausibility for s in scores) / count
        mean_n = sum(s.novelty for s in scores) / count
        mean_s = sum(s.specificity for s in scores) / count
        overall = mean_p * 0.4 + mean_n * 0.3 + mean_s * 0.3

        dims = [
            {"dimension": "plausibility", "score": mean_p},
            {"dimension": "novelty", "score": mean_n},
            {"dimension": "specificity", "score": mean_s},
        ]
        worst = sorted(dims, key=lambda d: d["score"])[:2]

        return SpeculationEvalReport(
            speculation_scores=scores,
            mean_plausibility=round(mean_p, 4),
            mean_novelty=round(mean_n, 4),
            mean_specificity=round(mean_s, 4),
            mean_no_hallucination=1.0,
            overall_score=round(overall, 4),
            worst_dimensions=worst,
            attributions=[
                f"{d['dimension']} ({d['score']:.2f}) → speculation_generation_prompt"
                for d in worst if d["score"] < 0.7
            ],
            timestamp=datetime.now().isoformat(),
        )
