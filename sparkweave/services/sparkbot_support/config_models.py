"""Configuration models and secret masking helpers for SparkBot."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

COMPETITION_DEMO_BOT_ID = "deep_learning_foundations_tutor"

_COMPETITION_DEMO_SOUL = """# Soul

你是「深度学习」课程的 AI 助教。

你的默认工作方式：

1. 先判断学生现在最应该完成的一步，不把工具清单直接丢给学生。
2. 回答时优先参考课程资料、学习画像、最近练习和学习效果报告。
3. 如果问题适合多智能体协作，要把任务拆给资料检索、讲解、出题、图解、评估等角色。
4. 每次回答后给出一个可执行下一步，并说明完成后会写回哪些学习证据。
5. 多模态资源要能围绕课件、图解、小测、语音讲解和学习报告组织起来。

语气：耐心、清楚、像高校课程助教；避免技术黑话，优先用学生能立即行动的语言。
"""


def _is_secret_field(name: str) -> bool:
    lowered = name.lower()
    return any(
        hint in lowered
        for hint in ("token", "password", "secret", "api_key", "apikey", "encrypt_key")
    )


def mask_channel_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        for key, item in value.items():
            if _is_secret_field(str(key)) and isinstance(item, str) and item:
                masked[key] = "***"
            else:
                masked[key] = mask_channel_secrets(item)
        return masked
    if isinstance(value, list):
        return [mask_channel_secrets(item) for item in value]
    return value


class SparkBotConfigModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class SparkBotMCPServerConfig(SparkBotConfigModel):
    """MCP server connection config accepted from old and NG bot configs."""

    type: Literal["stdio", "sse", "streamableHttp"] | None = None
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    tool_timeout: int = 30
    enabled_tools: list[str] = Field(default_factory=lambda: ["*"])


class SparkBotWebSearchConfig(SparkBotConfigModel):
    """Web search config accepted from old SparkBot configs."""

    provider: str = "brave"
    api_key: str = ""
    base_url: str = ""
    max_results: int = 5


class SparkBotWebToolsConfig(SparkBotConfigModel):
    """Web tool config accepted from old SparkBot configs."""

    proxy: str | None = None
    search: SparkBotWebSearchConfig = Field(default_factory=SparkBotWebSearchConfig)
    fetch_max_chars: int = 50_000


class SparkBotExecToolConfig(SparkBotConfigModel):
    """Shell exec config accepted from old SparkBot configs."""

    timeout: int = 60
    path_append: str = ""


class SparkBotToolsConfig(SparkBotConfigModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    web: SparkBotWebToolsConfig = Field(default_factory=SparkBotWebToolsConfig)
    exec_config: SparkBotExecToolConfig = Field(
        default_factory=SparkBotExecToolConfig,
        alias="exec",
        serialization_alias="exec",
    )
    restrict_to_workspace: bool = True
    mcp_servers: dict[str, SparkBotMCPServerConfig] = Field(default_factory=dict)


class SparkBotAgentConfig(SparkBotConfigModel):
    max_tool_iterations: int = 4
    tool_call_limit: int = 5
    max_tokens: int = 8192
    context_window_tokens: int = 65_536
    temperature: float = 0.1
    reasoning_effort: str | None = None
    memory_window: int | None = Field(default=None, exclude=True)
    team_max_workers: int = 5
    team_worker_max_iterations: int = 25


class SparkBotHeartbeatConfig(SparkBotConfigModel):
    enabled: bool = True
    interval_s: int = 30 * 60


class BotConfig(SparkBotConfigModel):
    name: str
    description: str = ""
    persona: str = ""
    channels: dict[str, Any] = Field(default_factory=dict)
    model: str | None = None
    auto_start: bool = False
    tools: SparkBotToolsConfig = Field(default_factory=SparkBotToolsConfig)
    agent: SparkBotAgentConfig = Field(default_factory=SparkBotAgentConfig)
    heartbeat: SparkBotHeartbeatConfig = Field(default_factory=SparkBotHeartbeatConfig)


def build_competition_demo_bot_config() -> BotConfig:
    """Return the stable SparkBot config used by the competition demo."""

    return BotConfig(
        name="深度学习课程助教",
        description="赛题主线课程助教：围绕深度学习课件，展示画像驱动、资料可追溯、多智能体资源生成和学习评估闭环。",
        persona=_COMPETITION_DEMO_SOUL,
        channels={
            "send_progress": True,
            "send_tool_hints": False,
            "web": {
                "enabled": True,
                "welcome_text": "我会先看你的学习画像和深度学习课件，再给出今天最应该完成的一步。",
                "rate_limit": 8,
            },
        },
        auto_start=False,
        heartbeat={"enabled": False, "intervalS": 900},
    )


class ChannelConfigModel(SparkBotConfigModel):
    pass


class WebConfig(ChannelConfigModel):
    enabled: bool = True
    welcome_text: str = "我会先看你的学习画像和深度学习课件，再给出今天最应该完成的一步。"
    rate_limit: int = 8


class TelegramConfig(ChannelConfigModel):
    enabled: bool = False
    token: str = ""
    allow_from: list[str] = Field(default_factory=list)
    proxy: str | None = None
    reply_to_message: bool = False
    group_policy: Literal["open", "mention"] = "mention"


class SlackDMConfig(ChannelConfigModel):
    enabled: bool = True
    policy: str = "open"
    allow_from: list[str] = Field(default_factory=list)
    webhook_url: str = ""


class SlackConfig(ChannelConfigModel):
    enabled: bool = False
    mode: str = "socket"
    webhook_path: str = "/slack/events"
    bot_token: str = ""
    app_token: str = ""
    user_token_read_only: bool = True
    reply_in_thread: bool = True
    react_emoji: str = "eyes"
    allow_from: list[str] = Field(default_factory=list)
    group_policy: str = "mention"
    group_allow_from: list[str] = Field(default_factory=list)
    dm: SlackDMConfig = Field(default_factory=SlackDMConfig)


class DiscordConfig(ChannelConfigModel):
    enabled: bool = False
    token: str = ""
    allow_from: list[str] = Field(default_factory=list)
    guild_id: str = ""
    gateway_url: str = "wss://gateway.discord.gg/?v=10&encoding=json"
    intents: int = 37377
    group_policy: Literal["mention", "open"] = "mention"


class DingTalkConfig(ChannelConfigModel):
    enabled: bool = False
    client_id: str = ""
    client_secret: str = ""
    allow_from: list[str] = Field(default_factory=list)


class EmailConfig(ChannelConfigModel):
    enabled: bool = False
    consent_granted: bool = False
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    imap_mailbox: str = "INBOX"
    imap_use_ssl: bool = True
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    from_address: str = ""
    auto_reply_enabled: bool = True
    poll_interval_seconds: int = 30
    mark_seen: bool = True
    max_body_chars: int = 12000
    subject_prefix: str = "Re: "
    allow_from: list[str] = Field(default_factory=list)


class FeishuConfig(ChannelConfigModel):
    enabled: bool = False
    app_id: str = ""
    app_secret: str = ""
    encrypt_key: str = ""
    verification_token: str = ""
    allow_from: list[str] = Field(default_factory=list)
    react_emoji: str = "THUMBSUP"
    group_policy: Literal["open", "mention"] = "mention"


class MatrixConfig(ChannelConfigModel):
    enabled: bool = False
    homeserver: str = "https://matrix.org"
    access_token: str = ""
    user_id: str = ""
    device_id: str = ""
    e2ee_enabled: bool = False
    sync_stop_grace_seconds: int = 2
    max_media_bytes: int = 20 * 1024 * 1024
    allow_from: list[str] = Field(default_factory=list)
    group_policy: Literal["open", "mention", "allowlist"] = "open"
    group_allow_from: list[str] = Field(default_factory=list)
    allow_room_mentions: bool = False


class MochatMentionConfig(ChannelConfigModel):
    require_in_groups: bool = False


class MochatGroupRule(ChannelConfigModel):
    require_mention: bool = False


class MochatConfig(ChannelConfigModel):
    enabled: bool = False
    base_url: str = "https://mochat.io"
    socket_url: str = ""
    socket_path: str = "/socket.io"
    socket_disable_msgpack: bool = False
    socket_reconnect_delay_ms: int = 1000
    socket_max_reconnect_delay_ms: int = 10000
    socket_connect_timeout_ms: int = 10000
    refresh_interval_ms: int = 30000
    watch_timeout_ms: int = 25000
    watch_limit: int = 100
    retry_delay_ms: int = 500
    max_retry_attempts: int = 0
    claw_token: str = ""
    agent_user_id: str = ""
    sessions: list[str] = Field(default_factory=list)
    panels: list[str] = Field(default_factory=list)
    allow_from: list[str] = Field(default_factory=list)
    mention: MochatMentionConfig = Field(default_factory=MochatMentionConfig)
    groups: dict[str, MochatGroupRule] = Field(default_factory=dict)
    reply_delay_mode: str = "non-mention"
    reply_delay_ms: int = 120000


class QQConfig(ChannelConfigModel):
    enabled: bool = False
    app_id: str = ""
    secret: str = ""
    allow_from: list[str] = Field(default_factory=list)
    msg_format: Literal["plain", "markdown"] = "plain"


class WecomConfig(ChannelConfigModel):
    enabled: bool = False
    bot_id: str = ""
    secret: str = ""
    allow_from: list[str] = Field(default_factory=list)
    welcome_message: str = ""


class WhatsAppConfig(ChannelConfigModel):
    enabled: bool = False
    bridge_url: str = "ws://localhost:3001"
    bridge_token: str = ""
    allow_from: list[str] = Field(default_factory=list)


class ChannelsConfig(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="allow")

    send_progress: bool = True
    send_tool_hints: bool = False
    transcription_api_key: str = ""
    web: WebConfig = Field(default_factory=WebConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    dingtalk: DingTalkConfig = Field(default_factory=DingTalkConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    matrix: MatrixConfig = Field(default_factory=MatrixConfig)
    mochat: MochatConfig = Field(default_factory=MochatConfig)
    qq: QQConfig = Field(default_factory=QQConfig)
    wecom: WecomConfig = Field(default_factory=WecomConfig)
    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)


__all__ = [
    "BotConfig",
    "ChannelConfigModel",
    "ChannelsConfig",
    "COMPETITION_DEMO_BOT_ID",
    "DiscordConfig",
    "DingTalkConfig",
    "EmailConfig",
    "FeishuConfig",
    "MatrixConfig",
    "MochatConfig",
    "MochatGroupRule",
    "MochatMentionConfig",
    "QQConfig",
    "SlackConfig",
    "SlackDMConfig",
    "SparkBotAgentConfig",
    "SparkBotConfigModel",
    "SparkBotExecToolConfig",
    "SparkBotHeartbeatConfig",
    "SparkBotMCPServerConfig",
    "SparkBotToolsConfig",
    "SparkBotWebSearchConfig",
    "SparkBotWebToolsConfig",
    "TelegramConfig",
    "WebConfig",
    "WecomConfig",
    "WhatsAppConfig",
    "_COMPETITION_DEMO_SOUL",
    "_is_secret_field",
    "build_competition_demo_bot_config",
    "mask_channel_secrets",
]
