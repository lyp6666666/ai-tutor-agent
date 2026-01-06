  


## 项目结构

```text
ai-tutor-agent2/
├── requirements.txt        # 依赖（fastapi, agentscope 等）
└── app/
    ├── main.py             # FastAPI 入口
    ├── api/                # 对外 HTTP / WS 接口
    │   ├── ingest.py       # 被动监听：接收课堂数据
    │   ├── command.py      # 主动任务：教师指令入口
    │   ├── summary.py      # 课后总结 / 知识点抽取入口
    │   ├── report.py       # 课堂表现报告入口
    │   ├── homework.py     # 作业批改接口（文本 / 图片）
    │   └── ws.py           # WebSocket：推送 agent 事件
    ├── core/               # 核心运行时
    │   ├── app_context.py  # 全局上下文（state + dispatcher + event_bus）
    │   ├── event_bus.py    # 会话内事件总线（推送给 WS）
    │   ├── state_manager.py# Session 状态与时间轴
    │   └── task_dispatcher.py # 任务调度器（模式切换、子 agent 调用）
    ├── agents/             # 各子智能体（AgentScope）
    │   ├── summarizer.py       # Lesson Summarizer
    │   ├── dictation.py        # Dictation Agent（骨架）
    │   ├── grader.py           # Homework Grader
    │   ├── observer.py         # Classroom Observer
    │   ├── proctor.py          # Proctor Agent（监考骨架，TODO: YOLOv8）
    │   ├── knowledge_extractor.py # Knowledge Extractor
    │   └── question_gen.py     # Question Generator（TODO: LLM 出题）
    ├── multimodal/         # 多模态缓存（目前辅助用）
    │   ├── text_buffer.py
    │   ├── audio_buffer.py
    │   └── video_buffer.py
    └── schema/             # 所有 API / 内部事件的结构定义（Pydantic）
        ├── ingest.py
        ├── command.py
        ├── summary.py
        ├── report.py
        ├── homework.py
        └── events.py
```

## 核心思想：

- 按 session_id 管理一节课的完整时间轴与内部状态。
- 被动监听层只负责 缓存与轻量结构化 ，不做重推理。
- 教师通过 IM 或 HTTP 显式发指令时，任务调度器切换到 主动高频推理模式 ，调度各子 AgentScope 智能体。



**运行模式与数据流**

**1. 被动监听（低频 / 低成本）**

- 接口：POST /api/v1/ingest/events
- 输入：IngestEvent（三类类型）

```json
{
  "session_id": "sess_1",
  "type": "im_message | asr_text | 
  video_event",
  "timestamp": 1710000000.0,
  "im":    { "sender_id": "stu_1", 
  "text": "老师好", "role": 
  "student" },
  "asr":   { "speaker": "teacher", 
  "text": "今天我们学习一般现在时" },
  "video": { "student_id": "stu_1", 
  "event": "HEAD_DOWN_FREQUENT" }
}
```

- 处理流程：
  - StateManager.append_event() 将事件追加到 SessionState.timeline。
  - TaskDispatcher.on_event()：
    - 调用 ClassroomObserver.on_event() 更新课堂参与度与注意力相关状态。
    - 如果当前有激活任务（例如听写），则把 IM 当作学生答案交给对应子模块。
    - 如果 IM 来自老师并带有 @AI 助教，自动抽取其中的命令文本，等价于调 /command。
- 输出：IngestResponse 中携带的 emitted_events，用于驱动上游 TTS/IM 组件（也会推送到 WebSocket）：

```json
{
  "ok": true,
  "emitted_events": [
    {
      "type": "tts_request",
      "timestamp": 1710000001.0,
      "payload": {
        "text": "apple",
        "task": "dictation",
        "index": 0,
        "total": 2
      }
    },
    {
      "type": "im_request",
      "timestamp": 1710000001.1,
      "payload": {
        "text": "请输入第 1/2 个单词的
        拼写",
        "task": "dictation"
      }
    }
  ]
}
```

**2. 主动任务模式（教师唤起）**

- 入口1：教师在 IM 里发：

```text
@AI 助教 开始单词听写
@AI 助教 生成课后总结
@AI 助教 停止听写
```

被动监听收到教师 IM 后，TaskDispatcher._is_teacher_command_im() 检测 im.is_teacher 或 im.role == "teacher" 且内容以 @AI 开头，自动提取命令正文并走 on_command()。

- 入口2：显式 HTTP 调用

```http
POST /api/v1/command
Content-Type: application/json
{
  "session_id": "sess_1",
  "teacher_id": "t_1",
  "command_text": "开始单词听写",
  "args": {
    "words": ["apple", "banana", 
    "orange"]
  }
}
```

- 任务调度逻辑（

  TaskDispatcher.on_command

  ）：

  - 开始单词听写 → 启用听写状态机（主动任务模式）。
  - 停止任务/停止听写/结束任务 → 停止当前任务。
  - 生成总结/输出课后总结 → 立即调用 LessonSummarizer 基于当前时间轴生成结构化总结。
  - 未识别命令 → 返回 agent_notice，reason=unknown_command。



## 核心子模块设计

### 1. 状态管理与时间轴（StateManager）
- 每个 session_id 对应一个 SessionState ：
```python
@dataclass
class SessionState:
    session_id: str
    created_at: float
    timeline: list[IngestEvent]
    dictation: DictationState
    observer: ObserverState
    active_task: str | None
```
- DictationState ：听写任务的进度与得分。
```python
@dataclass
class DictationState:
    active: bool
    words: list[str]
    index: int
    attempts: int
    correct: int
    last_prompted_at: float | None
```
- ObserverState ：课堂表现相关统计。
```python
@dataclass
class ObserverState:
    utterances_by_user: dict[str, int]
    correct_answers_by_user: dict[str, int]
    total_answers_by_user: dict[str, int]
    focus_events: list[dict]
```
- 线程安全：每个 session 有独立的 asyncio.Lock ，保证并发写安全。
### 2. 任务调度器（TaskDispatcher）
负责把“低级事件 + 教师指令”转成具体智能体行为与输出事件，是 Agent 层的“大总管”。

事件处理（被动监听入口）

```python
async def on_event(self, event: IngestEvent) 
-> list[EmittedEvent]:
    session = await self.state_manager.
    get_session(event.session_id)
    outputs = []
    outputs += await self.observer.on_event
    (session, event)

    if event.type == "im_message" and event.im 
    is not None:
        if self._is_teacher_command_im(event.
        im):
            cmd_text = self.
            _extract_command_from_im(event.im.
            get("text", ""))
            cmd_req = CommandRequest(...)
            cmd_res = await self.on_command
            (cmd_req)
            outputs += cmd_res.emitted_events

    if session.active_task == "dictation" and 
    event.type == "im_message":
        outputs += await self._on_dictation_im
        (session, event.im["text"], event.im.
        get("sender_id"))

    return outputs
```
命令处理（主动模式入口）

- 匹配命令类型（听写 / 停止 / 生成总结）。
- 启动或停止状态机，调用具体子 Agent（目前听写逻辑在调度器内实现，TTS/IM 由上游按 EmittedEvent 执行）。
- 对总结命令：直接调用 LessonSummarizer.summarize() ，输出结构化 JSON 包在 summary_ready 事件里。
### 3. 单词听写 Agent（Dictation Agent）
业务流程

1. 教师发指令：
```text
@AI 助教 开始单词听写
# 或携带单词列表：
@AI 助教 开始单词听写：apple, banana, orange
```
2. TaskDispatcher.on_command ：
- 初始化 DictationState ：
  
  - words = 来自 args.words 或从命令文本里解析（ 听写：xxx,yyy ）。
  - index = 0; attempts = 0; correct = 0; active = True
  - session.active_task = "dictation"
- 发送第一轮 TTS + IM 提示：
```json
[
  {
    "type": "tts_request",
    "payload": {
      "text": "apple",
      "task": "dictation",
      "index": 0,
      "total": 3
    }
  },
  {
    "type": "im_request",
    "payload": {
      "text": "请输入第 1/3 个单词的拼写",
      "task": "dictation"
    }
  }
]
```
3. 学生通过 IM 回复：
```json
{
  "session_id": "sess_1",
  "type": "im_message",
  "timestamp": 1710000002.0,
  "im": { "sender_id": "stu_1", "text": 
  "apple" }
}
```
4. TaskDispatcher._on_dictation_im ：
- 对比答案，更新 attempts/correct。
- 输出 dictation_result 事件：
```json
{
  "type": "dictation_result",
  "payload": {
    "sender_id": "stu_1",
    "expected": "apple",
    "answer": "apple",
    "correct": true,
    "index": 0
  }
}
```
- index + 1，继续下一轮 tts_request + im_request ，直到全部完成。
- 所有单词完成后，输出 dictation_finished ：
```
{
  "type": "dictation_finished",
  "payload": {
    "attempts": 2,
    "correct": 2,
    "accuracy": 1.0
  }
}
```
app/agents/dictation.py 里额外提供了一个基于 AgentScope 的 DictationAgent 骨架类，目前由调度器驱动，后续你可以把听写流程迁移到这个 Agent 里，由 LLM 生成更灵活的提示语等。

### 4. 作业批改 Agent（Homework Grader）
- 对外接口在 app/api/homework.py ：
（1）文本作业批改

```
POST /api/v1/homework/grade_text
Content-Type: multipart/form-data

session_id: sess_1
student_id: stu_1
student_answer: "I goes to school every day."
standard_answer: "I go to school every day."
```
- 内部实现： HomeworkGrader.grade_text 使用 difflib.SequenceMatcher 做简单相似度计算：
  
  - ratio → [0, 1] ，再映射到 0~100 分。
  - score >= 90 判为正确。
- 返回结构：
```
{
  "ok": true,
  "session_id": "sess_1",
  "student_id": "stu_1",
  "result": {
    "correct": false,
    "score": 85,
    "reason": "与标准答案存在差异"
  }
}
```
（2）图片作业批改（预留 OCR）

```htt
POST /api/v1/homework/grade_image
Content-Type: multipart/form-data

session_id: sess_1
student_id: stu_1
standard_answer: "x^2 + y^2 = 1"
image: <file>
```
- HomeworkGrader.grade_image(image_bytes, standard_answer) 中已用 TODO 标明，需要你后续接入 OCR（如 PaddleOCR）：
```python
async def grade_image(self, image_bytes: 
bytes, standard_answer: str) -> dict:
    # TODO: 接入OCR（如PaddleOCR）后将图片转文本，
    再复用 grade_text
    return {"correct": False, "score": 0, 
    "reason": "TODO: 图片作业批改需要OCR能力"}
```
### 5. 监考 Agent（Proctor Agent）
- 目标：持续接收视频或下游检测结果，识别：
  - 多人（多人出现）
  - 离开座位
  - 频繁低头
- 当前设计：服务本身不直接跑 YOLO，而是接收“已检测好的事件”作为 video_event 进入时间轴；监考 Agent 是 AgentScope 骨架：
```
class ProctorAgent(AgentBase):
    async def reply(...):
        # TODO: 接入YOLOv8/OpenCV，对视频帧进行多
        人/离开座位/低头等检测
        return Msg(..., content="TODO: 监考能力
        需要接入视频检测模型。")
```
- 你可以后续在这里：
  - 加入 OpenCV 读取视频帧。
  - 调 YOLOv8 进行目标检测与行为识别。
  - 将检测结果包装成 video_event ，比如：
```
{
  "session_id": "sess_1",
  "type": "video_event",
  "timestamp": 1710000000.0,
  "video": {
    "student_id": "stu_1",
    "event": "SUSPECT_CHEATING",   // 或 
    MULTIPLE_PERSON, LEAVE_SEAT, 
    HEAD_DOWN_FREQUENT
    "raw": { /* YOLO 检测结果 */ }
  }
}
```
- 告警事件可以按你最初定义的结构由上游监考服务产生，也可以在本服务内生成 EmittedEvent，例如：
```
{
  "type": "SUSPECT_CHEATING",
  "timestamp": 1710000001.0,
  "payload": {
    "student_id": "stu_1",
    "reason": "HEAD_DOWN_FREQUENT"
  }
}
```
### 6. 课堂表现记录 Agent（Classroom Observer）
实现文件： app/agents/observer.py

- 在 on_event 中：
  
  - IM 事件：
    - utterances_by_user[sender_id]++
  - video_event：
    - 把 {timestamp, event, student_id} 追加到 focus_events
- 课后通过 build_report(session, student_id) 生成报告：
```
ClassroomReport(
  student_id="stu_1",
  participation="active | normal | silent",  # 
  按发言次数阈值划分
  focus_score=0.82,                          # 
  基于监考“坏事件”次数扣分
  utterances=10,
  answer_accuracy=0.9
)
```
- 对外接口： POST /api/v1/report
```
{
  "session_id": "sess_1",
  "student_id": "stu_1"
}
```
返回：

```
{
  "ok": true,
  "session_id": "sess_1",
  "report": {
    "student_id": "stu_1",
    "participation": "active",
    "focus_score": 0.82,
    "utterances": 12,
    "answer_accuracy": 0.9
  }
}
```
注意：注意力评分目前是简单规则：每个坏事件（ MULTIPLE_PERSON , LEAVE_SEAT , HEAD_DOWN_FREQUENT ）扣 0.1，可根据实际监考策略增强。

### 7. 课程总结 & 知识点抽取（Lesson Summarizer + Knowledge Extractor） 时间轴构建
- LessonSummarizer._build_timeline_text 将 session.timeline 里的最近 ~400 条事件拼成一段有标签的文本：
```
[IM][stu_1] 老师好
[ASR] 今天我们学习一般现在时
[IM][teacher] 知识点：一般现在时的基本结构
[VIDEO] HEAD_DOWN_FREQUENT
...
``` 规则版 summarizer（AgentScope AgentBase）
- _RuleBasedSummarizer 继承 AgentBase ， reply() 直接对文本做非常轻量的摘要（取最后几条关键行拼接）。 LLM 版 summarizer（AgentScope ReActAgent）
- 若环境变量中存在 OPENAI_API_KEY ，则构建一个基于 AgentScope 的 ReActAgent ：
```
return ReActAgent(
    name="LessonSummarizerLLM",
    sys_prompt="你是课堂AI助教，擅长结构化课后总结。
    ",
    model=OpenAIChatModel
    (model_name=model_name, api_key=api_key, 
    stream=False),
    formatter=OpenAIChatFormatter(),
    memory=InMemoryMemory(),
)
```
- 给它一个指令，要求输出 JSON：
```
你是课堂AI助教。请基于时间轴文本，输出JSON：
{"summary": "...", "knowledge_points": ["...
"], "homework_suggestion": ["..."]}

时间轴：
...
```
- 再从 LLM 返回中用正则提取 JSON 并 json.loads ，如果解析失败就回退到规则版 summarizer + 简单的知识点抽取。
```



