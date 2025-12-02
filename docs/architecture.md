````markdown
# VoiceBridge Core 架构说明（初稿）

> 目标：为**教学 / VRChat / 会议 / 跨语言交流**提供统一的语音交互内核。  
> 本文档面向：产品合作者、后端开发者、桌面端开发者。

## 当前实现状态（Phase 0）

- 已落地：核心类型（Session/Utterance/Profile）、配置加载、基础 logging、Profile 示例、CLI smoke 脚本。
- 未落地：ASR/LLM/TTS 具体实现、Audio I/O、Agent 自动发声逻辑。
- 快速体验：`python3 -m pip install -r requirements.txt` → `cp config/settings.example.yml config/settings.yml` → `python3 cli/smoke.py --profile Teaching`。更多说明见仓库根目录的 README。

---

## 1. 产品定位 & 目标

### 1.1 一句话定位

**VoiceBridge Core = 一个统一的「听 → 懂 → 帮你想 → 说」语音交互引擎**，  
上层可以挂接不同场景模式（Profile）：

- Teaching Mode：教学 / 一对一辅导 / 讲解
- VRChat Mode：声带受损/不便开麦玩家的 TTS 语音助手
- Meeting Mode：会议总结 / 跨语言交流
- Social / Casual Mode：轻量对话、陪伴、游戏语音等

### 1.2 核心目标

- 通过统一的底层架构，**最大化代码复用**，不同场景只需：
  - 更换 Profile 配置
  - 更换 Prompt 模板
  - 调整策略（自动建议 / 自动发声 / 是否需要审核）
- 让用户在复杂对话场景中只需：
  - **听** → **选择 / 修正** → **确认发声**  
  而不需要大量打字或高负荷口头表达。

### 1.3 非目标（当前阶段）

- 不自行实现虚拟声卡驱动（使用 VB-CABLE / BlackHole 等成熟方案）
- 不从零实现 ASR / TTS / LLM 模型（全部走 API 或现成开源模型）
- 不做复杂 UI/前端（当前以 CLI/TUI + 简单桌面浮窗为主）

---

## 2. 核心使用场景（高层）

### 2.1 Teaching Mode（教学 & 辅导）

- 输入：
  - 老师键盘输入
  - 学生语音（选配：Zoom/Discord 声音捕获 + ASR）
- 系统功能：
  - 自动生成教学讲解稿（可直接朗读）
  - 自动解释学生错误 / 问题（分步骤解释）
  - 自动总结当节课的要点 / 比喻 / 举例
  - 提供简短回复建议（如「换个例子再解释」）
- 输出：
  - 老师克隆声线 + 教学语气的 TTS
  - 课堂记录 / Transcript

### 2.2 VRChat / 声带受损玩家模式

- 输入：
  - 玩家键盘输入（短句 / 热键短语）
  - 对方语音（通过虚拟声卡 loopback 捕获 + ASR）
- 系统功能：
  - 自动生成自然的候选回复
  - 支持跨语言翻译 / 解释对方说的话
  - 根据 Profile 自动选语气（友好 / 调侃 / 认真）
- 输出：
  - TTS → 虚拟麦克风（其他玩家听到就是“说话”）
  - 可选：字幕浮窗（自己看到）

### 2.3 Meeting / Cross-Language Mode（后期）

- 输入：
  - 会议音频（系统捕获）
  - 本地用户的文字或简短语音
- 功能：
  - 实时转写 & 翻译
  - 自动总结 / action items
  - 日志记录、回放
- 输出：
  - TTS（本地用户或代理发言）
  - 会议纪要文本

---

## 3. Domain Model（领域模型）

统一抽象不同场景的共性对象。

### 3.1 Session（会话）

一次连续的互动过程（上课 / 一场游戏 / 一次会议）：

```python
class Session:
    id: str
    profile: Profile
    started_at: datetime
    ended_at: datetime | None
    utterances: list[Utterance]
    suggestions: list[Suggestion]
    metadata: dict
````

### 3.2 Participant（参与者）

```python
class Participant:
    id: str
    role: Literal["local_user", "remote_user", "agent"]
    display_name: str
    language: str | None
```

### 3.3 Utterance（话语）

一句话 / 一段用户表达（语音或文字）：

```python
class Utterance:
    speaker: Participant
    text: str
    language: str | None
    timestamp: datetime
    source: Literal["mic", "system_audio", "keyboard", "agent"]
```

### 3.4 Suggestion（回复建议）

系统生成的候选回复：

```python
class Suggestion:
    text: str
    style: str  # "teaching", "friendly", "playful", ...
    confidence: float
    auto_send: bool  # Agent 模式下是否可自动发出
```

### 3.5 Profile（场景配置）

Teaching / VRChat / Meeting 等不同模式的配置集合：

```python
class Profile:
    name: str
    input_mode: str  # "manual", "asr", "manual+asr"
    tts_backend: str
    default_voice: str
    output_device: str
    reply_strategy: ReplyStrategy
    prompts: dict[str, str]  # e.g. "explain", "suggestion", "summarize"
```

```python
class ReplyStrategy:
    auto_suggest: bool
    auto_speak: bool
    max_suggestion_length: int
    allow_agent_mode: bool
```

---

## 4. 分层架构（后端）

> 从下往上，由底层工具 → 服务封装 → 对话管理 → 理解/规划 → 场景策略。

### 概览图（逻辑层次）

```text
┌─────────────────────────────┐
│         UI / Client         │  ← TUI / 桌面浮窗 / VRChat 插件
└─────────────▲───────────────┘
              │
┌─────────────┴───────────────┐
│         Orchestrator        │  ← 统一流程控制（输入→ASR→LLM→建议→TTS）
└─────────────▲───────────────┘
              │
┌─────────────┴───────────────┐
│  Conversation & Profile      │  ← Session / Transcript / Profile 策略
└─────────────▲───────────────┘
              │
┌───────┬─────┴───────┬───────┐
│  ASR  │  LLM/NLP     │  TTS  │  ← 语音理解/语言生成/语音合成服务
└──▲────┴───────▲──────┴──▲───┘
   │            │          │
┌──┴────────────┴──────────┴───┐
│      Audio I/O & Infra        │  ← 系统音频、config、logging、types
└──────────────────────────────┘
```

---

## 5. Layer 0：基础设施（Infra）

### 5.1 Config & Logging

* 统一读取配置文件（YAML/JSON）：

  * API key（OpenAI、ElevenLabs 等）
  * Audio 设备映射
  * Profile 列表
* Logging：

  * 交互日志（用户说了什么 / 回了什么）
  * ASR/LLM/TTS 请求响应时间
  * 错误记录

### 5.2 Types

将上面的 `Session / Utterance / Suggestion / Profile` 定义为 `dataclass` / Pydantic 模型，这些类型在整个项目中复用。

---

## 6. Layer 1：服务封装（Services）

统一对各种 API/模型的调用方式，隐藏底层细节。

### 6.1 ASRService

```python
class ASRService:
    def transcribe(
        self,
        audio_bytes: bytes,
        language_hint: str | None = None,
    ) -> Utterance:
        ...
```

实现：

* `WhisperASRService`（OpenAI Whisper or local faster-whisper）
* 未来可以添加 `AzureASRService` 等

### 6.2 LLMService

```python
class LLMService:
    def complete(self, messages: list[dict], model: str, **kwargs) -> str:
        ...

    def structured(self, messages: list[dict], model: str, schema: type):
        """使用 JSON / Pydantic schema 返回结构化结果"""
        ...
```

### 6.3 TTSService

```python
class TTSService:
    def synthesize(
        self,
        text: str,
        voice_id: str,
        style: str | None = None,
    ) -> bytes:
        """返回音频 bytes（wav/mp3）"""
        ...
```

实现：

* `ElevenLabsTTSService`
* `OpenAITTSService`
* 日后可接入 Azure TTS

### 6.4 TranslationService（可选，初期可由 LLM 模拟）

```python
class TranslationService:
    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        ...
```

---

## 7. Layer 2：Audio I/O（音频输入输出）

统一对音频设备的访问抽象。

### 7.1 输出设备（TTS 播放）

```python
class AudioOutputBackend:
    def list_output_devices(self) -> list[str]: ...
    def play_to_device(self, device_name: str, audio_bytes: bytes) -> None: ...
```

实现：

* Windows:

  * `WindowsAudioOutputBackend`（WASAPI + sounddevice / pyaudiowpatch）
* macOS:

  * `MacAudioOutputBackend`（CoreAudio + sounddevice）

### 7.2 输入设备 / Loopback（ASR 捕获）

```python
class AudioInputBackend:
    def list_input_devices(self) -> list[str]: ...
    def capture_loopback(
        self,
        device_name: str,
    ) -> Iterable[bytes]:
        """持续产生音频帧，用于 ASR"""
        ...
```

实现：

* Windows:

  * 使用 WASAPI loopback 抓取 VRChat/Discord 输出或 VB-CABLE Output
* macOS:

  * 使用 BlackHole/Loopback 作为中转设备

**说明**：
虚拟声卡本身（VB-CABLE / BlackHole）不由本项目实现，而是作为外部前置依赖；本层只负责与这些设备打交道。

---

## 8. Layer 3：会话与上下文管理（Conversation Core）

负责所有场景共用的 Transcript 和上下文逻辑。

```python
class ConversationSession:
    def __init__(self, profile: Profile):
        self.profile = profile
        self.utterances: list[Utterance] = []
        self.suggestions: list[Suggestion] = []

    def add_utterance(self, utt: Utterance) -> None: ...
    def add_suggestion(self, s: Suggestion) -> None: ...
    def get_recent_context(self, max_turns: int = 8) -> list[Utterance]: ...
```

用途：

* Teaching：

  * 用于生成课堂总结 / 章节总结
  * 帮助解释时引用学生之前的问题
* VRChat：

  * 用于给出“合适的”社交回复建议
* Meeting：

  * 用于最终生成会议纪要、行动点

---

## 9. Layer 4：理解与规划（Understanding & Planning）

### 9.1 意图识别（Intent Analysis）

```python
class IntentResult(BaseModel):
    intent: Literal["question", "statement", "smalltalk", "complaint", "request_help", "other"]
    topic: str
    emotion: Literal["neutral", "confused", "frustrated", "happy", "serious"]
    ask_for_clarification: bool
```

函数示例：

```python
def analyze_intent(llm: LLMService, session: ConversationSession) -> IntentResult:
    """
    使用最近几条 utterances 调用 LLM，返回对当前轮对话的理解。
    """
    ...
```

### 9.2 Explanation Engine（解释引擎）

基于 Profile + Intent：

* Teaching：

  * 用讲解型 prompt 生成分步骤解释、举例
* VRChat：

  * 用“简单解释 + 社交语气”的 prompt 重述对方说的内容给本地用户
* Meeting：

  * 用总结型 prompt 提取要点

### 9.3 Suggestion Engine（生成回复建议）

```python
class SuggestionEngine:
    def __init__(self, profile: Profile, llm: LLMService): ...

    def generate_suggestions(
        self,
        session: ConversationSession,
        intent: IntentResult,
    ) -> list[Suggestion]:
        ...
```

不同 Profile 只需要更换内部使用的 prompt 模板：

* Teaching：偏“解释 / 提示下一步该讲什么”
* VRChat：偏“短句 / 自然口语 / 情感柔和”
* Meeting：偏“简短 + 正式 + 任务导向”

---

## 10. Layer 5：Profile & Policy（场景策略）

### 10.1 Profile 配置文件（YAML 示例）

```yaml
# profiles/teaching.yml
name: "Teaching"
input_mode: "manual+asr"
tts_backend: "elevenlabs"
default_voice: "shu_teaching"
output_device: "system_speakers"
reply_strategy:
  auto_suggest: true
  auto_speak: false
  max_suggestion_length: 120
  allow_agent_mode: false
prompts:
  explain: |
    你是一名耐心的计算机辅导老师，面对的是基础不牢但聪明的学生。
    用分步骤、类比和例子解释下面的内容，适合直接朗读。
  suggestion: |
    根据下面的对话，为老师生成 2 条候选回答，用口语化、易懂风格。
  summarize: |
    总结本节对话中出现的关键概念和易错点。
```

```yaml
# profiles/vrchat.yml
name: "VRChat"
input_mode: "asr"
tts_backend: "elevenlabs"
default_voice: "shu_casual"
output_device: "vb_cable_input"
reply_strategy:
  auto_suggest: true
  auto_speak: true
  max_suggestion_length: 60
  allow_agent_mode: true
prompts:
  suggestion: |
    你是一个友好、轻松、稍微幽默的 VRChat 玩家。
    根据下面的对话，生成 2 条候选回复，简短、不尴尬、自然。
  translate: |
    把对方说的内容翻译成中文，并用一句话解释他的语气和意图。
```

---

## 11. Layer 6：Orchestrator（流程编排）

统一处理：

1. 输入（keyboard / audio）
2. ASR（可选）
3. 意图识别
4. 建议生成
5. 是否自动发声（agent / 手动）
6. 调用 TTS & AudioOutput

示例骨架：

```python
class Orchestrator:
    def __init__(
        self,
        profile: Profile,
        services: ServiceBundle,
        audio_io: AudioIOBundle,
    ):
        self.profile = profile
        self.session = ConversationSession(profile)
        self.asr = services.asr
        self.llm = services.llm
        self.tts = services.tts
        self.sugg_engine = SuggestionEngine(profile, self.llm)
        self.audio_out = audio_io.output

    def handle_remote_audio(self, audio_chunk: bytes):
        # 1. ASR
        utt = self.asr.transcribe(audio_chunk)
        self.session.add_utterance(utt)

        # 2. 理解
        intent = analyze_intent(self.llm, self.session)

        # 3. 生成建议
        suggestions = self.sugg_engine.generate_suggestions(self.session, intent)
        for s in suggestions:
            self.session.add_suggestion(s)

        # 4. 根据策略决定是否自动发声
        if self.profile.reply_strategy.auto_speak and suggestions:
            chosen = suggestions[0]
            audio = self.tts.synthesize(chosen.text, voice_id=self.profile.default_voice)
            self.audio_out.play_to_device(self.profile.output_device, audio)

    def handle_local_text(self, text: str):
        """处理本地用户输入（教学模式下的 /explain 等）"""
        ...
```

Agent 模式的 “1–2 秒可打断窗口” 可以在这里实现：
在生成建议后启动计时，如果用户在窗口期内修改/取消，则不 `auto_speak`。

---

## 12. 项目结构建议

```text
voicebridge-core/
  docs/
    architecture.md
    profiles.md
  config/
    profiles/
      teaching.yml
      vrchat.yml
      meeting.yml
    settings.yml
  core/
    types.py            # Session, Utterance, Suggestion, Profile, ReplyStrategy
    config.py           # 加载配置
    logging.py
  services/
    asr_base.py
    asr_whisper.py
    llm_base.py
    llm_openai.py
    tts_base.py
    tts_elevenlabs.py
    translate_base.py
  audio_io/
    backend_base.py
    backend_windows.py
    backend_macos.py
  conversation/
    session_manager.py
  understanding/
    intent_analyzer.py
    explanation_engine.py
    suggestion_engine.py
  orchestrator/
    orchestrator.py
  cli/
    tts_console.py      
```

---

## 13. 开发阶段规划（从下至上）

### Phase 0：基础类型 & 配置

* 实现 `core/types.py`（Session/Utterance/…）
* 实现 `core/config.py`（Profile & settings 加载）
* 实现基础 logging

### Phase 1：外部服务封装

* `LLMService`（OpenAI）
* `TTSService`（ElevenLabs + OpenAI）
* `ASRService`（先用 Whisper API）

### Phase 2：Conversation & Suggestion（纯文字流程）

* `ConversationSession`
* `analyze_intent`
* `SuggestionEngine`
* 在 CLI 中实现：

  * 输入文本 → LLM → 建议 → TTS 播放

### Phase 3：引入 Profile 概念

* teaching.yml / vrchat.yml
* 把 SuggestionEngine 和 intent 分析改为使用 Profile 的 prompts

### Phase 4：接入 Audio I/O（初步）

* WindowsAudioBackend（播放 + 简单 loopback 测试）
* Orchestrator 增加 `handle_remote_audio` 的逻辑

### Phase 5：Agent 模式（试验）

* 定义 AgentPolicy
* Orchestrator 中加入 auto_speak/override window 的逻辑

### Phase 6：封装成可分发的核心库

* 将核心逻辑从 CLI 中抽离为 `voicebridge-core` 包
* CLI / 桌面客户端 / VRChat 助手都以此为依赖

---

## 14. 给协作开发者的说明

* **如果你是后端开发：**
  重点关注 `core/`, `services/`, `conversation/`, `understanding/`, `orchestrator/`

  * 请不要在业务逻辑中硬编码 Profile / Prompt，而是放到 config/profile 文件中。
  * 所有与外部服务（OpenAI/ElevenLabs）的调用，都应通过 `services/` 内的封装类实现。

* **如果你是桌面/前端开发：**
  重点关注：

  * Orchestrator 提供的接口（如 `handle_remote_audio`, `handle_local_text`）
  * Audio I/O backend 对设备的抽象方法
  * 你可以将 CLI/TUI 替换为桌面 UI，但后端逻辑保持不变。

* **如果你是产品设计 / Prompt 工程方向：**

  * 可以在 `config/profiles/*.yml` 中持续优化：

    * 不同模式下的 prompt 模板
    * 默认语气与声线
    * Auto-speak 策略（是否直接“代为发言”）
  * 可以新建 Profile（例如 “Conference”, “Interpreter”）而不需要改动底层代码。

---

> 本文档是架构初稿，后续可按实际实现情况调整。
> 建议：每完成一个 Phase，即补充对应部分的实现细节与示例。

```
::contentReference[oaicite:0]{index=0}
```
