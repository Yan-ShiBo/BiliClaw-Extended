"""Per-layer update functions for the ProfileUpdatePipeline.

Each layer has its own update logic: Surface uses computation, Interest
delegates to PreferenceAnalyzer, Role/Values/Core use LLM with diff protection.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openbiliclaw.memory.manager import MemoryManager
    from openbiliclaw.soul.preference_analyzer import PreferenceAnalyzer
    from openbiliclaw.soul.profile import OnionProfile
    from openbiliclaw.soul.profile_builder import ProfileBuilder

from .pipeline import LayerUpdateResult, OnionLayer

logger = logging.getLogger(__name__)


async def update_layer(
    *,
    layer: OnionLayer,
    signals: list[dict[str, object]],
    profile: OnionProfile,
    memory: MemoryManager,
    preference_analyzer: PreferenceAnalyzer,
    profile_builder: ProfileBuilder,
) -> LayerUpdateResult:
    """Dispatch to the appropriate layer updater."""
    updater = _LAYER_UPDATERS.get(layer)
    if updater is None:
        return LayerUpdateResult(layer=layer, changed=False)
    return await updater(
        signals=signals,
        profile=profile,
        memory=memory,
        preference_analyzer=preference_analyzer,
        profile_builder=profile_builder,
    )


# ---------------------------------------------------------------------------
# Surface layer — computational, no LLM
# ---------------------------------------------------------------------------


async def _update_surface(
    *,
    signals: list[dict[str, object]],
    profile: OnionProfile,
    **_: Any,
) -> LayerUpdateResult:
    """Update surface layer from behavioral signals using pure computation."""
    changes: list[str] = []

    # Count event types for style inference
    view_count = 0
    search_count = 0
    for sig in signals:
        payload = sig.get("payload", {})
        if isinstance(payload, dict):
            event_type = str(payload.get("event_type", ""))
            if event_type == "view":
                view_count += 1
            elif event_type == "search":
                search_count += 1

    # If we have enough behavioral data, adjust depth preference
    if view_count >= 2:
        old_depth = profile.surface.style.depth_preference
        # More search events relative to views suggests deeper engagement
        depth_signal = min(1.0, 0.5 + (search_count / max(view_count, 1)) * 0.3)
        new_depth = round(old_depth * 0.7 + depth_signal * 0.3, 2)
        if abs(new_depth - old_depth) > 0.05:
            profile.surface.style.depth_preference = new_depth
            changes.append(f"depth_preference: {old_depth:.2f} → {new_depth:.2f}")

    return LayerUpdateResult(
        layer=OnionLayer.SURFACE,
        changed=bool(changes),
        changes=changes,
        signals_consumed=len(signals),
        trigger="行为模式分析",
        evidence=f"{view_count} views, {search_count} searches",
        timestamp=datetime.now().isoformat(),
    )


# ---------------------------------------------------------------------------
# Interest layer — LLM + tree merge
# ---------------------------------------------------------------------------


async def _update_interest(
    *,
    signals: list[dict[str, object]],
    profile: OnionProfile,
    memory: MemoryManager,
    preference_analyzer: PreferenceAnalyzer,
    **_: Any,
) -> LayerUpdateResult:
    """Update interest layer by delegating to PreferenceAnalyzer."""
    # Convert signals back to event format for PreferenceAnalyzer
    events: list[dict[str, Any]] = []
    for sig in signals:
        payload = sig.get("payload", {})
        if isinstance(payload, dict):
            events.append(dict(payload))

    if not events:
        return LayerUpdateResult(layer=OnionLayer.INTEREST, changed=False)

    preference_layer = memory.get_layer("preference")
    existing_preference = dict(preference_layer.data)

    try:
        updated_preference = await preference_analyzer.analyze_events(
            events=events,
            existing_preference=existing_preference,
        )
    except Exception:
        logger.exception("PreferenceAnalyzer failed during interest update")
        return LayerUpdateResult(layer=OnionLayer.INTEREST, changed=False)

    # Persist flat preference (unchanged pipeline)
    preference_layer.data.clear()
    preference_layer.data.update(updated_preference)
    preference_layer.save()

    # Update the onion interest + surface layers from flat preference
    profile.populate_from_flat_preference(updated_preference)

    # Sync cognitive_style (not modeled in PreferenceLayer, bypasses populate)
    cs = updated_preference.get("cognitive_style")
    if isinstance(cs, list):
        profile.surface.cognitive_style = [str(s) for s in cs if s]

    # Detect changes
    changes: list[str] = []
    old_interests = {
        item.get("name", ""): float(item.get("weight", 0))
        for item in (existing_preference.get("interests") or [])
        if isinstance(item, dict)
    }
    new_interests = {
        item.get("name", ""): float(item.get("weight", 0))
        for item in (updated_preference.get("interests") or [])
        if isinstance(item, dict)
    }
    for name in new_interests:
        if name not in old_interests:
            changes.append(f"新增兴趣: {name} ({new_interests[name]:.2f})")
        elif abs(new_interests[name] - old_interests.get(name, 0)) > 0.15:
            changes.append(
                f"兴趣权重变化: {name} {old_interests[name]:.2f} → {new_interests[name]:.2f}"
            )

    old_dislikes = set(
        existing_preference.get("disliked_topics") or []
        if isinstance(existing_preference.get("disliked_topics"), list) else []
    )
    new_dislikes = set(
        updated_preference.get("disliked_topics") or []
        if isinstance(updated_preference.get("disliked_topics"), list) else []
    )
    for topic in new_dislikes - old_dislikes:
        changes.append(f"新增讨厌: {topic}")

    # Feed speculative_interests to speculator as seed candidates
    speculative_seeds = updated_preference.get("speculative_interests")
    if isinstance(speculative_seeds, list) and speculative_seeds:
        try:
            from openbiliclaw.soul.speculator import InterestSpeculator

            data_dir = getattr(memory, "_data_dir", None)
            if data_dir:
                speculator = InterestSpeculator(llm_service=None, data_dir=data_dir)
                added = speculator.ingest_seeds(speculative_seeds)
                if added:
                    changes.append(f"注入 {added} 条猜测兴趣种子")
        except Exception:
            logger.debug("Speculator seed ingestion skipped", exc_info=True)

    return LayerUpdateResult(
        layer=OnionLayer.INTEREST,
        changed=bool(changes),
        changes=changes,
        signals_consumed=len(signals),
        trigger="偏好分析",
        evidence=f"分析了 {len(events)} 条事件",
        timestamp=datetime.now().isoformat(),
    )


# ---------------------------------------------------------------------------
# Role layer — LLM with diff protection
# ---------------------------------------------------------------------------


async def _update_role(
    *,
    signals: list[dict[str, object]],
    profile: OnionProfile,
    memory: MemoryManager,
    **_: Any,
) -> LayerUpdateResult:
    """Update role layer (life_stage, current_phase) from accumulated signals.

    Uses LLM with diff-protection: only apply if LLM explicitly proposes change.
    """
    # Collect evidence from signals
    evidence_parts: list[str] = []
    for sig in signals:
        payload = sig.get("payload", {})
        if isinstance(payload, dict):
            content = str(payload.get("content", ""))
            if content:
                evidence_parts.append(content)

    if not evidence_parts:
        return LayerUpdateResult(layer=OnionLayer.ROLE, changed=False)

    # TODO: Add LLM delta prompt call when prompts_pipeline.py is ready
    # For now, buffer signals and return unchanged
    return LayerUpdateResult(
        layer=OnionLayer.ROLE,
        changed=False,
        changes=[],
        signals_consumed=len(signals),
        trigger="角色信号积累",
        evidence="; ".join(evidence_parts[:3]),
        timestamp=datetime.now().isoformat(),
    )


# ---------------------------------------------------------------------------
# Values layer — LLM with delta-only updates
# ---------------------------------------------------------------------------


async def _update_values(
    *,
    signals: list[dict[str, object]],
    profile: OnionProfile,
    **_: Any,
) -> LayerUpdateResult:
    """Update values layer using LLM delta (add/remove, max 1 per cycle)."""
    evidence_parts: list[str] = []
    for sig in signals:
        payload = sig.get("payload", {})
        if isinstance(payload, dict):
            content = str(payload.get("content", ""))
            if content:
                evidence_parts.append(content)

    if not evidence_parts:
        return LayerUpdateResult(layer=OnionLayer.VALUES, changed=False)

    # TODO: Add LLM delta prompt call when prompts_pipeline.py is ready
    return LayerUpdateResult(
        layer=OnionLayer.VALUES,
        changed=False,
        changes=[],
        signals_consumed=len(signals),
        trigger="价值观信号积累",
        evidence="; ".join(evidence_parts[:3]),
        timestamp=datetime.now().isoformat(),
    )


# ---------------------------------------------------------------------------
# Core layer — LLM with strongest diff protection
# ---------------------------------------------------------------------------


async def _update_core(
    *,
    signals: list[dict[str, object]],
    profile: OnionProfile,
    **_: Any,
) -> LayerUpdateResult:
    """Update core layer (traits, needs, MBTI) with strong diff protection."""
    evidence_parts: list[str] = []
    for sig in signals:
        payload = sig.get("payload", {})
        if isinstance(payload, dict):
            content = str(payload.get("content", ""))
            if content:
                evidence_parts.append(content)

    if not evidence_parts:
        return LayerUpdateResult(layer=OnionLayer.CORE, changed=False)

    # TODO: Add LLM delta prompt call when prompts_pipeline.py is ready
    return LayerUpdateResult(
        layer=OnionLayer.CORE,
        changed=False,
        changes=[],
        signals_consumed=len(signals),
        trigger="核心信号积累",
        evidence="; ".join(evidence_parts[:3]),
        timestamp=datetime.now().isoformat(),
    )


# ---------------------------------------------------------------------------
# Portrait regeneration
# ---------------------------------------------------------------------------


async def regenerate_portrait(
    *,
    profile: OnionProfile,
    profile_builder: ProfileBuilder,
    memory: MemoryManager,
) -> str:
    """Regenerate personality_portrait from current profile state.

    Only called when Core or Values layer actually changes.
    Returns the new portrait text, or empty string on failure.
    """
    from .profile import awareness_note_to_dict, insight_hypothesis_to_dict

    try:
        legacy_profile = await profile_builder.build(
            history=[],
            preference=memory.get_layer("preference").data,
            awareness_notes=[
                awareness_note_to_dict(n) for n in profile.recent_awareness[:5]
            ],
            active_insights=[
                insight_hypothesis_to_dict(i) for i in profile.active_insights[:5]
            ],
        )
        return legacy_profile.personality_portrait
    except Exception:
        logger.exception("Failed to regenerate portrait")
        return ""


# ---------------------------------------------------------------------------
# Updater dispatch table
# ---------------------------------------------------------------------------

_LAYER_UPDATERS = {
    OnionLayer.SURFACE: _update_surface,
    OnionLayer.INTEREST: _update_interest,
    OnionLayer.ROLE: _update_role,
    OnionLayer.VALUES: _update_values,
    OnionLayer.CORE: _update_core,
}
