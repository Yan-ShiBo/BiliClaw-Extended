# Project Identity

This repository is the active BiliClaw Extended fork:

- GitHub: `https://github.com/Yan-ShiBo/BiliClaw-Extended`
- Local workspace: `D:\BiliClaw`
- Python package and CLI: `openbiliclaw`
- Browser extension package: `openbiliclaw-extension`

The package and CLI names intentionally remain compatible with the upstream project. Public documentation, repository URLs, issue links, and current setup instructions should point to `Yan-ShiBo/BiliClaw-Extended`.

## What Changed in This Fork

- Local Windows deployment has been validated around port `8420`.
- The setup flow supports local or server Ollama for LLM and embedding.
- Default embedding for Douyin likes uses local `qwen3-embedding:8b`.
- Server LLM usage is treated as on-demand heavy analysis, not an always-on requirement.
- Douyin supports two accounts in one backend instance through separate browser login/import passes.
- Douyin liked videos are stored in a local ChromaDB vector database.
- Bilibili, Xiaohongshu, and secondary Douyin account signals receive mild balancing in profile analysis.
- The first large Douyin account receives mild old-tail recency decay.
- Extension versions are bumped with functional updates so the loaded browser version is easy to verify.

## Repository Hygiene

Keep these out of Git:

- `config.toml`
- Cookies and API keys
- Server credentials
- `data/`
- `logs/`
- `.tmp/`
- Model download logs

Historical upstream planning documents remain under `docs/archive/` for reference. Current user-facing behavior should be documented in active docs outside the archive.
