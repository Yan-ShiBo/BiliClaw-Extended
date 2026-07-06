# Local Deployment

This guide describes the current Windows local deployment used by `Yan-ShiBo/BiliClaw-Extended`.

## 1. Install

```powershell
git clone https://github.com/Yan-ShiBo/BiliClaw-Extended.git D:\BiliClaw
cd D:\BiliClaw
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
copy config.example.toml config.toml
```

Do not commit `config.toml`.

## 2. Start Backend

```powershell
openbiliclaw serve-api --host 0.0.0.0 --port 8420
```

Expected local endpoints:

- `http://127.0.0.1:8420/setup/`
- `http://127.0.0.1:8420/web`
- `http://127.0.0.1:8420/api/health`
- `http://127.0.0.1:8420/api/runtime-status`

## 3. Load Browser Extension

1. Open `chrome://extensions/`.
2. Enable Developer Mode.
3. Click `Load unpacked`.
4. Select `D:\BiliClaw\extension`.
5. Confirm version `0.3.159`.

After every extension code change, reload the extension in `chrome://extensions/` and refresh the target platform tab.

## 4. Model Setup

Recommended split:

- Embedding: local Ollama `qwen3-embedding:8b`.
- Heavy analysis: server Ollama large model, loaded only when needed.

Example:

```toml
[llm]
default_provider = "ollama"

[llm.ollama]
model = "qwen3.5:122b"
base_url = "http://YOUR_SERVER_IP:11434/v1"

[llm.embedding]
provider = "ollama"
model = "qwen3-embedding:8b"
base_url = "http://127.0.0.1:11434/v1"
```

## 5. Official Ollama LAN Listening

Temporary port forwarding works for short sessions, but a permanent server setup should bind Ollama to the LAN interface.

Linux systemd override:

```bash
sudo systemctl edit ollama
```

Use:

```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
curl http://SERVER_IP:11434/api/tags
```

Keep the server on a trusted LAN or protect it with a reverse proxy/firewall. Ollama itself does not provide password authentication.

## 6. Verification

```powershell
Invoke-WebRequest http://127.0.0.1:8420/api/health
Invoke-WebRequest http://127.0.0.1:8420/api/runtime-status
Invoke-WebRequest http://127.0.0.1:8420/web
```

For extension verification, trigger one platform task from a logged-in tab and confirm the backend receives a task result.
