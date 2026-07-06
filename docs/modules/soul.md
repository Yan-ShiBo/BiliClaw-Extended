# Soul Module

## Overview

The Soul module turns raw behavior events into a long-term personal profile. It is responsible for preference extraction, layered profile updates, cognition notes, speculation, avoidance learning, manual edits, and the compact profile context used by discovery and recommendation.

Main path: `src/openbiliclaw/soul/`.

## Implemented Features

| Feature | Main Code | Status |
| --- | --- | --- |
| Preference analysis | `preference_analyzer.py` | Converts behavior events into interests, dislikes, styles, and source mix |
| Source/account weighting | `PreferenceAnalyzer._apply_source_signal_weights` | Adds `metadata.analysis_weight` for Bilibili/XHS/Douyin balancing |
| Chunked LLM analysis | `PreferenceAnalyzer._analyze_events_chunked` | Splits large event sets to fit model context |
| Source mix tracking | `PreferenceAnalyzer.compute_source_platform_mix` | Stores weighted platform contribution in the preference layer |
| Layered profile | `profile.py`, `pipeline.py`, `layer_updaters.py` | Maintains surface, interest, role, values, and core layers |
| Soul engine | `engine.py` | Public profile API, feedback processing, manual edits, and writeback |
| Cognition cycle | `cognition_cycle.py`, `awareness_analyzer.py`, `insight_analyzer.py` | Builds awareness notes and insight hypotheses |
| Interest consolidation | `consolidator.py`, `category_migration.py` | Merges duplicates and keeps taxonomy stable |
| Speculative interests | `speculator.py` | Generates and confirms possible new interests |
| Avoidance learning | `avoidance_speculator.py`, `negative_exemplars.py` | Learns disliked or fatigue-prone areas |
| Profile rendering | `profile_builder.py`, `tone.py` | Builds compact Markdown/JSON profile summaries |

## Public API

### `PreferenceAnalyzer.analyze_events`

```python
preference = await analyzer.analyze_events(
    events,
    existing_preference=current_preference,
)
```

Returns a normalized preference dictionary. Before the LLM call, events are compacted and weighted. The compact metadata can include:

```json
{
  "source_platform": "douyin",
  "account_id": "account2",
  "analysis_weight": 1.15
}
```

### `PreferenceAnalyzer.compute_source_platform_mix`

```python
mix = PreferenceAnalyzer.compute_source_platform_mix(events)
```

Returns a normalized map such as:

```json
{
  "douyin": 0.62,
  "bilibili": 0.21,
  "xiaohongshu": 0.10,
  "youtube": 0.07
}
```

If `metadata.analysis_weight` is present, the mix uses weighted counts.

### `SoulEngine.analyze_events`

```python
result = await soul_engine.analyze_events(events)
```

Runs preference analysis and updates the profile write path used by API, CLI, and initialization flows.

### `SoulProfile`

`SoulProfile` serializes and renders the layered profile. It is the object used by discovery and recommendation to understand current taste, avoidances, and style preferences.

## Source Weighting Policy

The current policy is deliberately small and transparent:

| Signal | Effect |
| --- | --- |
| Bilibili events | Mild boost |
| Xiaohongshu events | Mild boost |
| Secondary Douyin account | Mild boost |
| First Douyin account older likes | Mild recency decay with a floor |
| Unknown sources | Neutral |

This is not a hard rule that forces recommendation output. It only helps the analyzer avoid overfitting to the largest imported source.

## Config Items

Soul behavior is mostly driven by runtime services and scheduler settings:

```toml
[llm.soul]
provider = ""
model = ""

[soul.preference]
satisfaction_filter_enabled = true

[scheduler]
profile_consolidation_enabled = true
profile_consolidation_interval_hours = 12
profile_consolidation_like_target_upper = 512
profile_consolidation_like_target_soft = 450
profile_consolidation_archive_enabled = true
```

Embedding is configured independently:

```toml
[llm.embedding]
provider = "ollama"
model = "qwen3-embedding:8b"
base_url = "http://127.0.0.1:11434/v1"
```

## Design Decisions

- Keep raw events local and only send compacted text to the selected LLM provider.
- Store account/source balancing in metadata so prompts and tests can reason about it directly.
- Use mild weighting rather than fixed quotas; real user behavior should still dominate.
- Keep embedding separate from chat LLM so large server models are not required for batch imports.
- Keep manual edits and feedback writeback inside the Soul engine, not in platform adapters.
