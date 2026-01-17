## AI Tutor Agent（课堂 AI 助教运行时）

基于 FastAPI 的课堂 AI 助教服务：
- 课堂进行中：接收实时数据帧并落 Redis（事实时间线）
- 后台：周期性生成阶段总结
- 课堂结束：异步生成课后最终报告
- 教师指令：结合课堂上下文调用火山方舟（Doubao）生成回复，通过 WebSocket 推送

## 快速启动

### 1) 准备依赖

- Python：3.12（见 `.python-version`）
- Redis：本地或云端均可
- 火山方舟 API Key：用于调用 `ARK_BASE_URL` 的 `chat/completions`

启动本地 Redis（可选）：

```bash
docker run --rm -p 6379:6379 redis:7-alpine
```

### 2) 配置环境变量

复制配置：

```bash
cp .env.example .env
```

编辑 `.env`，至少填好：
- `ARK_API_KEY`
- `REDIS_URL`（默认本地 Redis 即可）

### 3) 安装并启动

```bash
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 配置项

配置由 `pydantic-settings` 从 `.env` + 环境变量读取，见 [settings.py](file:///Users/bytedance/lyp/own/ai-tutor-agent/ai-tutor-agent/app/core/settings.py#L7-L21)：

- `REDIS_URL`：默认 `redis://localhost:6379/0`
- `ARK_BASE_URL`：默认 `https://ark.cn-beijing.volces.com/api/v3`
- `ARK_API_KEY`：必填
- `ARK_MODEL`：默认 `doubao-seed-1-8-251228`
- `STAGE_SUMMARY_MIN_INTERVAL_S`：阶段总结最小间隔（秒）
- `STAGE_SUMMARY_MIN_CHARS`：触发阶段总结的最小文本长度
- `STAGE_SUMMARY_MAX_UTTERANCES`：阶段总结窗口内最多取多少条发言

## 架构与数据流

应用入口在 [app.main:app](file:///Users/bytedance/lyp/own/ai-tutor-agent/ai-tutor-agent/app/main.py#L12-L29)，核心上下文在 [AppContext](file:///Users/bytedance/lyp/own/ai-tutor-agent/ai-tutor-agent/app/core/app_context.py#L21-L157)：

- 事实存储：Redis（[RedisFactStore](file:///Users/bytedance/lyp/own/ai-tutor-agent/ai-tutor-agent/app/infra/redis_fact_store.py#L21-L166)）
- 阶段总结调度：后台任务轮询 RUNNING 课堂（[StageSummaryScheduler](file:///Users/bytedance/lyp/own/ai-tutor-agent/ai-tutor-agent/app/core/schedulers.py#L11-L101)）
- LLM 调用：火山方舟 Chat Completions 轻封装（[ArkChatClient](file:///Users/bytedance/lyp/own/ai-tutor-agent/ai-tutor-agent/app/llm/ark_client.py#L38-L93)）

## 项目结构

```text
ai-tutor-agent/
├── app/
│   ├── main.py                      FastAPI 应用入口，挂载 /api/v1 路由
│   ├── api/                         HTTP / WebSocket 对外接口
│   │   ├── classroom.py             课堂：open/end + realtime WS + 查询接口
│   │   ├── agent.py                 指令入口：/agent/command
│   │   ├── ws.py                    事件订阅 WS：/ws/{session_id}
│   │   ├── command.py               预留接口（当前未挂载到 app.main）
│   │   ├── ingest.py                预留接口（当前未挂载到 app.main）
│   │   ├── summary.py               预留接口（当前未挂载到 app.main）
│   │   ├── report.py                预留接口（当前未挂载到 app.main）
│   │   └── homework.py              预留接口（当前未挂载到 app.main）
│   ├── core/                        运行时核心：上下文、调度、事件、配置
│   │   ├── app_context.py           进程级上下文（Redis/LLM/Scheduler/EventBus）
│   │   ├── settings.py              配置加载（.env + 环境变量）
│   │   ├── schedulers.py            阶段总结调度器（后台任务）
│   │   ├── summarization.py         阶段/课后总结与指令回复（LLM Prompt + 解析）
│   │   ├── event_bus.py             会话内事件总线（给 /ws/{session_id} 推送）
│   │   ├── classroom_session_manager.py 课堂会话管理（内存状态/锁）
│   │   ├── asr_client.py            ASR 客户端占位（当前仅校验 audio_chunk）
│   │   ├── state_manager.py         旧版状态管理（当前未在主流程使用）
│   │   └── task_dispatcher.py       旧版任务分发（当前未在主流程使用）
│   ├── infra/
│   │   └── redis_fact_store.py      Redis 事实存储与时间线读写
│   ├── llm/
│   │   └── ark_client.py            火山方舟 Chat API Client（多模态 input_*）
│   ├── schema/                      Pydantic 数据结构（请求/响应/事件）
│   ├── agents/                      旧版 AgentScope Agents（当前未接入主流程）
│   └── multimodal/                  多模态缓冲工具（预留）
├── tests/
│   └── manual_e2e.py                端到端调试脚本（open/realtime/command/end）
├── .env.example                     环境变量模板
├── pyproject.toml                   项目元信息与依赖（uv sync 读取）
├── requirements.txt                 兼容依赖列表
├── uv.lock                          依赖锁文件
└── main.py                          占位入口（不用于启动服务）
```

## 对外接口（/api/v1）

### 课堂生命周期

- `POST /api/v1/classroom/open`：开课
- `WS /api/v1/classroom/realtime`：实时接入课堂帧（当前支持 `mock_text` 调试）
- `POST /api/v1/classroom/end`：结束课堂（异步生成 final_report）
- `GET /api/v1/classroom/{session_id}/stage_summaries`：查询阶段总结
- `GET /api/v1/classroom/{session_id}/final_report`：查询课后报告

实现见 [classroom.py](file:///Users/bytedance/lyp/own/ai-tutor-agent/ai-tutor-agent/app/api/classroom.py#L21-L66)。

### 教师指令

- `POST /api/v1/agent/command`：指令入口，服务端会读取最近课堂上下文调用 LLM，然后通过事件 WS 推送回复

实现见 [agent.py](file:///Users/bytedance/lyp/own/ai-tutor-agent/ai-tutor-agent/app/api/agent.py#L11-L15)。

### 事件订阅（推送回复/报告）

- `WS /api/v1/ws/{session_id}`：订阅事件流（例如 `im_request`、`final_report_ready`）

实现见 [ws.py](file:///Users/bytedance/lyp/own/ai-tutor-agent/ai-tutor-agent/app/api/ws.py#L10-L20)。

## 本地测试

### 1) 端到端脚本（推荐）

```bash
python tests/manual_e2e.py
```

脚本会：
- open classroom
- 通过 `classroom/realtime` 发送两条 `mock_text` 帧
- 调用 `agent/command`（回复走 `/ws/{session_id}`）
- end classroom（触发课后报告异步生成）

见 [manual_e2e.py](file:///Users/bytedance/lyp/own/ai-tutor-agent/ai-tutor-agent/tests/manual_e2e.py#L150-L235)。

### 2) curl（HTTP）

```bash
BASE="http://127.0.0.1:8000"
SESSION_ID="sess_001"

curl -sS -X POST "$BASE/api/v1/classroom/open" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id":"'"$SESSION_ID"'",
    "course_id":"c_1",
    "course_name":"英语课",
    "teacher":{"teacher_id":"t_1","teacher_name":"张老师"},
    "start_time": 1730000000.0
  }'

curl -sS -X POST "$BASE/api/v1/agent/command" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id":"'"$SESSION_ID"'",
    "teacher_id":"t_1",
    "instruction":"请基于本节课内容给我一段课中提醒话术",
    "image_url": null
  }'

curl -sS -X POST "$BASE/api/v1/classroom/end" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"'"$SESSION_ID"'","end_time":1730003600.0}'

curl -sS "$BASE/api/v1/classroom/$SESSION_ID/stage_summaries"
curl -sS "$BASE/api/v1/classroom/$SESSION_ID/final_report"
```

### 3) WebSocket（websocat / Apifox）

监听事件：

```bash
websocat -t "ws://127.0.0.1:8000/api/v1/ws/sess_001"
```

发送 realtime 帧（音频字段是 base64 字符串；当前实现只校验可解码，真正 ASR 尚未接入；需要进入上下文请带 `mock_text`）：

```bash
printf '%s\n' '{
  "session_id":"sess_001",
  "user_id":"stu_1",
  "user_name":"小明",
  "role":"student",
  "timestamp": 1730000001.0,
  "audio_chunk":"AAAAAA==",
  "is_last": true,
  "mock_text":"老师我不太懂第三人称单数要不要加s？"
}' | websocat -t "ws://127.0.0.1:8000/api/v1/classroom/realtime"
```

Apifox 可直接建 WebSocket 请求，发送同样的 JSON 文本帧。

## 已知限制

- 实时 ASR：当前 [VolcengineAsrWsClient](file:///Users/bytedance/lyp/own/ai-tutor-agent/ai-tutor-agent/app/core/asr_client.py#L15-L39) 为占位实现，`realtime` 仅校验 `audio_chunk` base64 可解码；落库文本主要依赖 `mock_text`。
- 阶段总结触发：需要满足最小间隔与最小字符数，否则不会生成（见 `STAGE_SUMMARY_*` 配置）。

## 常见问题

- 启动报 `缺少 ARK_API_KEY`：确认根目录存在 `.env` 且包含 `ARK_API_KEY`，并在项目根目录启动服务。
- 阶段总结一直为空：检查课堂是否有足够 `mock_text`，以及 `STAGE_SUMMARY_MIN_CHARS` 是否过高。
- final_report 为空：`/classroom/end` 会异步生成，稍等后再查询，或监听 `/ws/{session_id}` 的 `final_report_ready` 事件。
