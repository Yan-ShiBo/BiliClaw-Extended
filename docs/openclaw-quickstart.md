# OpenClaw 接入指南

> 给 OpenClaw 和维护者的完整落地说明：怎么部署 OpenBiliClaw、怎么初始化、怎么让 OpenClaw 调用、以及日常怎么用。

## 适用场景

当你希望 OpenClaw 在当前仓库里直接调用 OpenBiliClaw 的学习与推荐能力时，使用这份指南。

当前接入方式不是 Python SDK 注册，而是：

1. 仓库根目录提供 workspace skill：`skills/openbiliclaw-adapter/SKILL.md`
2. skill 通过 JSON CLI bridge 调用：`src/openbiliclaw/integrations/openclaw/cli.py`
3. CLI bridge 再调用内部 adapter operation

## 部署策略

推荐按目标机器能力决定：

1. 目标机器有 Docker：优先 Docker 部署
2. 目标机器没有 Docker：退回本地 Python 部署

这个判断很直接，因为 OpenClaw 最终只需要两件事：

1. 能发现仓库里的 workspace skill
2. 能执行 skill 要求的命令

## 前置条件

- 已克隆当前仓库
- 目标机器可用 Python 3.11+
- 可以访问当前配置所需的 LLM provider
- 准备好 B 站 Cookie，或能在交互式终端里现场输入
- 如果走 Docker 路径，目标机器上还需要可用的 Docker / Docker Compose

## 方案 A：Docker 优先

这是推荐方案，适合长期运行 OpenBiliClaw 后端。

### 1. 启动后端容器

在仓库根目录执行：

```bash
docker compose up -d --build
```

当前 compose 定义见：

- `docker-compose.yml`
- `Dockerfile`

默认行为：

- 容器名：`openbiliclaw-backend`
- 对外端口：`8420`
- 运行时目录：`/app/runtime`
- 配置、数据、日志分别持久化在 Docker volumes 中

### 2. 完成首次初始化

容器启动后，必须先做一次初始化：

```bash
docker exec -it openbiliclaw-backend openbiliclaw init
```

> ⏱  **首次运行预计 2–5 分钟**。LLM 单次响应可能就要 10–30s，全程会打印进度，不要以为卡住了。

`init` 是 v0.3.5+ 的 4 阶段交互式向导，会自动检测缺什么并按需补齐：

1. **Phase 1 — LLM 服务选择**：菜单首选「本地 Ollama」（免费 / 离线 / 无需 API Key）；其他云厂商按需选；「OpenAI 协议兼容自建网关」是单独的菜单项。
2. **Phase 2 — 给所选服务填配置**：每个选项只问该选项需要的字段（Ollama 只问模型名；云厂商问 Key + 模型；OpenAI 协议兼容问 Base URL + Key + 模型）。
3. **Phase 3 — Embedding（独立提问）**：4 选 1（跟随主 LLM / Ollama bge-m3 / 自定义 OpenAI 兼容 / 其他 provider）。
4. **Phase 4 — Per-module 覆盖**（高级，默认跳过）。

接着引导你贴 B 站 Cookie（向导内有 F12 → Network 取 cookie 的 5 步教程），最后才进入真正的 init 阶段：

1. 拉取 B 站历史 / 收藏 / 关注（≈ 20–60s）
2. 分析偏好（LLM 调用，≈ 30–90s）
3. 生成初始画像（LLM 调用，≈ 30–60s）
4. 自动补首轮内容池（多策略并发 + LLM 评估，≈ 1–3 分钟）

如果当前终端**不是**交互式（CI / 服务器脚本），`init` 不会等待输入，而是直接报错——这是为了避免把脚本挂死。这时改用 `python3 scripts/agent_bootstrap.py --provider ... --llm-api-key ... --bilibili-cookie ...`（详见 [docs/agent-install.md](agent-install.md)）。

### 3. 给 OpenClaw 保留一个本地 workspace

即使后端跑在 Docker 里，OpenClaw 仍需要能看到当前仓库，因为它要发现：

- `skills/openbiliclaw-adapter/SKILL.md`

同时，宿主机最好保留一套轻量 Python 环境，方便 OpenClaw 或维护者执行 bridge / doctor 命令：

```bash
# 推荐：使用 uv（更快）
uv sync

# 或使用传统 venv
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 方案 B：本地部署

当目标机器没有 Docker 时，直接全本地部署。

在仓库根目录执行：

```bash
# 推荐：使用 uv（更快）
uv sync
cp config.example.toml config.toml

# 或使用传统 venv
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp config.example.toml config.toml
```

然后初始化：

```bash
openbiliclaw init
```

> ⏱  **首次运行预计 2–5 分钟**。同 Docker 路径，触发同一份 4 阶段交互式向导（LLM → Embedding → Cookie），后跑实际 init（拉历史 / 生成画像 / 首轮发现）。

如果你想跳过交互式向导（自动化场景），用 `scripts/agent_bootstrap.py` 的命令行 flag 一次性把所有字段传进去——见 [docs/agent-install.md](agent-install.md)。

## OpenClaw 如何发现并调用

OpenClaw 当前应直接发现仓库里的 workspace skill：

- `skills/openbiliclaw-adapter/SKILL.md`

这个 skill 不直接实现推荐逻辑，而是要求 OpenClaw 调下面的 CLI bridge：

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli <command> [flags]
```

已支持的命令：

- `sync-account`
- `get-profile`
- `get-delight` — 检查是否有惊喜推荐
- `next-probe` — 获取下一个待确认的猜测兴趣方向
- `chat --message "..." [--session openclaw]` — 苏格拉底式对话，一问一答，自动回写画像
- `runtime-status`
- `recommend --limit 5`
- `recommend --limit 5 --refresh-if-needed`
- `submit-feedback --recommendation-id 7 --feedback-type like`
- `listen` — 长连接推送 (`delight.candidate` + `interest.probe`)
- `doctor`
- `emit-skill-descriptors`

## 首次初始化后要做什么

不管是 Docker 还是本地部署，初始化完成后都建议做一轮自检。

### Docker 路径最小自检

```bash
docker exec -it openbiliclaw-backend openbiliclaw profile
uv run python -m openbiliclaw.integrations.openclaw.cli doctor
uv run python -m openbiliclaw.integrations.openclaw.cli get-profile
uv run python -m openbiliclaw.integrations.openclaw.cli recommend --limit 3
```

### 本地路径最小自检

```bash
openbiliclaw profile
uv run python -m openbiliclaw.integrations.openclaw.cli doctor
uv run python -m openbiliclaw.integrations.openclaw.cli get-profile
uv run python -m openbiliclaw.integrations.openclaw.cli recommend --limit 3
```

期望结果：

1. `profile` 能读到画像或至少给出初始化后状态
2. `doctor` 返回 `skill_pack_exists: true`
3. `get-profile` 返回 `{"ok": true, "data": ...}`
4. `recommend --limit 3` 返回推荐列表

## OpenClaw 日常使用流程

推荐给 OpenClaw 的常规使用顺序如下。

### 1. 读当前画像

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli get-profile
```

### 2. 确认猜测兴趣（主动追问）

先看有没有待确认的猜测兴趣方向：

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli next-probe
```

如果返回了一条假设，OpenClaw 应把 `question` 字段展示给用户，然后把用户的回答通过 `chat` 回传：

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli chat \
  --message "嗯对，最近在看很多参数化设计的东西"
```

苏格拉底式对话支持多轮——每次 `chat` 都会返回一个新的追问/回应，并且对话内容会自动回写进灵魂画像。

### 3. 取推荐

优先走快路径：

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli recommend --limit 3
```

### 4. 写反馈

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli submit-feedback \
  --recommendation-id 12 \
  --feedback-type like
```

如果是评论型反馈：

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli submit-feedback \
  --recommendation-id 12 \
  --feedback-type comment \
  --note "方向对，但我想看更深一点。"
```

### 5. 查看运行时状态

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli runtime-status
```

### 6. 低频做账户同步

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli sync-account
```

## OpenClaw 调用约定

给 OpenClaw 的规则建议保持为：

1. 优先用 `recommend --limit <n>`，这是快路径
2. 只有明确需要新鲜度检查时，才加 `--refresh-if-needed`
3. 解析 CLI 返回 JSON，不要依赖自然语言输出
4. 如果返回 `{ "ok": false, ... }`，直接上抛错误，不要继续串后续动作
5. 对 `comment` 反馈，必须带 `--note`
6. 把 `doctor` 当成接线排障入口，而不是日常业务命令

## 常见问题

### 1. 不确定该走 Docker 还是本地

按目标机能力判断：

- 有 Docker：优先 Docker
- 没 Docker：本地部署

### 2. `doctor` 失败

优先检查：

- 当前目录是不是仓库根目录
- 虚拟环境是否已激活
- 依赖是否已安装
- `src/openbiliclaw/integrations/openclaw/cli.py` 是否存在
- `skills/openbiliclaw-adapter/SKILL.md` 是否存在

### 3. `get-profile` 或 `recommend` 报未初始化

说明还没有完成初始化：

Docker：

```bash
docker exec -it openbiliclaw-backend openbiliclaw init
```

本地：

```bash
openbiliclaw init
```

### 4. 显式 refresh 太慢

这是预期风险之一。OpenClaw 交互默认应走快路径：

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli recommend --limit 3
```

只有在用户明确要求更强新鲜度时，才触发：

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli recommend --limit 3 --refresh-if-needed
```
