"""Provider catalog and lookup helpers for runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

IFLYTEK_SPARK_MODEL = "spark-x"
IFLYTEK_SPARK_X2_BASE_URL = "https://spark-api-open.xf-yun.com/x2/"
IFLYTEK_SPARK_X15_BASE_URL = "https://spark-api-open.xf-yun.com/v2/"
IFLYTEK_MAAS_CODING_MODEL = "astron-code-latest"
IFLYTEK_MAAS_CODING_BASE_URL = "https://maas-coding-api.cn-huabei-1.xf-yun.com/v2"
IFLYTEK_MAAS_CODING_ANTHROPIC_URL = "https://maas-coding-api.cn-huabei-1.xf-yun.com/anthropic"


@dataclass(frozen=True)
class ProviderSpec:
    """Provider metadata used by NG config and LLM calls."""

    name: str
    keywords: tuple[str, ...]
    env_key: str
    display_name: str = ""
    backend: str = "openai_compat"
    env_extras: tuple[tuple[str, str], ...] = ()
    is_gateway: bool = False
    is_local: bool = False
    detect_by_key_prefix: str = ""
    detect_by_base_keyword: str = ""
    default_api_base: str = ""
    strip_model_prefix: bool = False
    supports_max_completion_tokens: bool = False
    supports_prompt_caching: bool = False
    default_model: str = ""
    model_options: tuple[str, ...] = ()
    model_overrides: tuple[tuple[str, dict[str, Any]], ...] = ()
    is_oauth: bool = False
    is_direct: bool = False
    credential_hint: str = ""
    model_hint: str = ""
    docs_url: str = ""

    @property
    def mode(self) -> str:
        if self.is_oauth:
            return "oauth"
        if self.is_direct:
            return "direct"
        if self.is_gateway:
            return "gateway"
        if self.is_local:
            return "local"
        return "standard"

    @property
    def label(self) -> str:
        return self.display_name or self.name


PROVIDER_ALIASES = {
    "azure": "azure_openai",
    "azure-openai": "azure_openai",
    "azureopenai": "azure_openai",
    "google": "gemini",
    "google_genai": "gemini",
    "claude": "anthropic",
    "openai_compatible": "custom",
    "volcenginecodingplan": "volcengine_coding_plan",
    "volcengineCodingPlan": "volcengine_coding_plan",
    "bytepluscodingplan": "byteplus_coding_plan",
    "byteplusCodingPlan": "byteplus_coding_plan",
    "github-copilot": "github_copilot",
    "openai-codex": "openai_codex",
    "iflytek": "iflytek_spark_ws",
    "xfyun": "iflytek_spark_ws",
    "xunfei": "iflytek_spark_ws",
    "spark": "iflytek_spark_ws",
    "sparkdesk": "iflytek_spark_ws",
    "iflytek_spark": "iflytek_spark_ws",
    "iflytek_ws": "iflytek_spark_ws",
    "xfyun_ws": "iflytek_spark_ws",
    "xunfei_ws": "iflytek_spark_ws",
    "spark_ws": "iflytek_spark_ws",
    "sparkdesk_ws": "iflytek_spark_ws",
    "spark_x2": "iflytek_spark_ws",
    "iflytek_x2": "iflytek_spark_ws",
    "xfyun_x2": "iflytek_spark_ws",
    "xunfei_x2": "iflytek_spark_ws",
    "x2": "iflytek_spark_ws",
    "iflytek_spark_x2": "iflytek_spark_ws",
    "spark_x15": "iflytek_spark_ws",
    "spark_x1_5": "iflytek_spark_ws",
    "iflytek_x15": "iflytek_spark_ws",
    "iflytek_x1_5": "iflytek_spark_ws",
    "xfyun_x15": "iflytek_spark_ws",
    "xfyun_x1_5": "iflytek_spark_ws",
    "xunfei_x15": "iflytek_spark_ws",
    "xunfei_x1_5": "iflytek_spark_ws",
    "x15": "iflytek_spark_ws",
    "x1_5": "iflytek_spark_ws",
    "x1.5": "iflytek_spark_ws",
    "iflytek_spark_x15": "iflytek_spark_ws",
    "maas": "iflytek_maas_coding",
    "iflytek_maas": "iflytek_maas_coding",
    "xfyun_maas": "iflytek_maas_coding",
    "xunfei_maas": "iflytek_maas_coding",
    "maas_coding": "iflytek_maas_coding",
    "iflytek_maas_code": "iflytek_maas_coding",
    "iflytek_coding": "iflytek_maas_coding",
    "xfyun_coding": "iflytek_maas_coding",
    "astron": "iflytek_maas_coding",
    "astron_code": "iflytek_maas_coding",
    "astron-code": "iflytek_maas_coding",
}


PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec("custom", (), "", display_name="Custom", is_direct=True),
    ProviderSpec(
        "azure_openai",
        ("azure", "azure_openai"),
        "",
        display_name="Azure OpenAI",
        backend="azure_openai",
        is_direct=True,
    ),
    ProviderSpec(
        "openrouter",
        ("openrouter",),
        "OPENROUTER_API_KEY",
        display_name="OpenRouter",
        is_gateway=True,
        detect_by_key_prefix="sk-or-",
        detect_by_base_keyword="openrouter",
        default_api_base="https://openrouter.ai/api/v1",
        supports_prompt_caching=True,
        default_model="openai/gpt-5.5",
        model_options=(
            "openai/gpt-5.5",
            "openai/gpt-5.4",
            "openai/gpt-5.4-mini",
            "anthropic/claude-opus-4-7",
            "anthropic/claude-sonnet-4-6",
            "google/gemini-3.5-flash",
            "deepseek/deepseek-v4-pro",
            "deepseek/deepseek-v4-flash",
        ),
        credential_hint="OpenRouter API Key",
        model_hint="聚合平台模型名通常保留 provider/model 前缀。",
        docs_url="https://openrouter.ai/docs",
    ),
    ProviderSpec(
        "aihubmix",
        ("aihubmix",),
        "OPENAI_API_KEY",
        display_name="AiHubMix",
        is_gateway=True,
        detect_by_base_keyword="aihubmix",
        default_api_base="https://aihubmix.com/v1",
        strip_model_prefix=True,
        default_model="gpt-5.5",
        model_options=(
            "gpt-5.5",
            "gpt-5.4-mini",
            "claude-opus-4-7",
            "gemini-3.5-flash",
            "deepseek-v4-flash",
        ),
        credential_hint="AiHubMix API Key",
        model_hint="如果平台模型清单更新，可直接手动输入新的模型 ID。",
        docs_url="https://docs.aihubmix.com",
    ),
    ProviderSpec(
        "siliconflow",
        ("siliconflow",),
        "OPENAI_API_KEY",
        display_name="SiliconFlow",
        is_gateway=True,
        detect_by_base_keyword="siliconflow",
        default_api_base="https://api.siliconflow.cn/v1",
        default_model="deepseek-ai/DeepSeek-R1",
        model_options=(
            "deepseek-ai/DeepSeek-R1",
            "deepseek-ai/DeepSeek-V3",
            "Qwen/Qwen3-235B-A22B",
            "Pro/zai-org/GLM-4.7",
        ),
        credential_hint="SiliconFlow API Key",
        model_hint="硅基流动会频繁上新，预设保留官方 OpenAI 接口示例模型，也支持手动输入模型广场 ID。",
        docs_url="https://docs.siliconflow.cn/cn/api-reference/chat-completions/chat-completions",
    ),
    ProviderSpec(
        "volcengine",
        ("volcengine", "volces", "ark"),
        "OPENAI_API_KEY",
        display_name="VolcEngine",
        is_gateway=True,
        detect_by_base_keyword="volces",
        default_api_base="https://ark.cn-beijing.volces.com/api/v3",
    ),
    ProviderSpec(
        "volcengine_coding_plan",
        ("volcengine-plan",),
        "OPENAI_API_KEY",
        display_name="VolcEngine Coding Plan",
        is_gateway=True,
        default_api_base="https://ark.cn-beijing.volces.com/api/coding/v3",
        strip_model_prefix=True,
    ),
    ProviderSpec(
        "byteplus",
        ("byteplus",),
        "OPENAI_API_KEY",
        display_name="BytePlus",
        is_gateway=True,
        detect_by_base_keyword="bytepluses",
        default_api_base="https://ark.ap-southeast.bytepluses.com/api/v3",
        strip_model_prefix=True,
    ),
    ProviderSpec(
        "byteplus_coding_plan",
        ("byteplus-plan",),
        "OPENAI_API_KEY",
        display_name="BytePlus Coding Plan",
        is_gateway=True,
        default_api_base="https://ark.ap-southeast.bytepluses.com/api/coding/v3",
        strip_model_prefix=True,
    ),
    ProviderSpec(
        "anthropic",
        ("anthropic", "claude"),
        "ANTHROPIC_API_KEY",
        display_name="Anthropic",
        backend="anthropic",
        default_api_base="https://api.anthropic.com/v1",
        supports_prompt_caching=True,
        default_model="claude-opus-4-7",
        model_options=(
            "claude-opus-4-7",
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001",
            "claude-opus-4-1-20250805",
            "claude-sonnet-4-20250514",
        ),
        credential_hint="ANTHROPIC_API_KEY",
        model_hint="Opus 适合复杂推理和 Agent，Sonnet 更适合日常速度/质量平衡。",
        docs_url="https://docs.claude.com/en/docs/about-claude/models/overview",
    ),
    ProviderSpec(
        "openai",
        ("openai", "gpt"),
        "OPENAI_API_KEY",
        display_name="OpenAI",
        default_api_base="https://api.openai.com/v1",
        supports_max_completion_tokens=True,
        default_model="gpt-5.5",
        model_options=(
            "gpt-5.5",
            "gpt-5.4",
            "gpt-5.4-mini",
            "gpt-5.4-nano",
            "gpt-5.2",
            "gpt-4.1",
            "gpt-4.1-mini",
        ),
        credential_hint="OPENAI_API_KEY",
        model_hint="复杂推理选 gpt-5.5；日常学习场景可选 gpt-5.4-mini / nano 降低延迟和成本。",
        docs_url="https://developers.openai.com/api/docs/models",
    ),
    ProviderSpec(
        "openai_codex",
        ("openai_codex", "codex"),
        "",
        display_name="OpenAI Codex",
        backend="openai_codex",
        is_oauth=True,
        default_api_base="https://chatgpt.com/backend-api",
    ),
    ProviderSpec(
        "github_copilot",
        ("github_copilot", "copilot"),
        "",
        display_name="GitHub Copilot",
        backend="github_copilot",
        is_oauth=True,
        default_api_base="https://api.githubcopilot.com",
        strip_model_prefix=True,
    ),
    ProviderSpec(
        "deepseek",
        ("deepseek",),
        "DEEPSEEK_API_KEY",
        display_name="DeepSeek",
        default_api_base="https://api.deepseek.com",
        default_model="deepseek-v4-flash",
        model_options=(
            "deepseek-v4-flash",
            "deepseek-v4-pro",
            "deepseek-chat",
            "deepseek-reasoner",
        ),
        credential_hint="DEEPSEEK_API_KEY",
        model_hint="deepseek-chat/reasoner 仍兼容，但官方已说明未来会弃用，优先使用 v4-flash / v4-pro。",
        docs_url="https://api-docs.deepseek.com/quick_start/pricing",
    ),
    ProviderSpec(
        "gemini",
        ("gemini",),
        "GEMINI_API_KEY",
        display_name="Gemini",
        default_api_base="https://generativelanguage.googleapis.com/v1beta/openai/",
        default_model="gemini-3.5-flash",
        model_options=(
            "gemini-3.5-flash",
            "gemini-3.1-pro-preview",
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash-lite",
        ),
        credential_hint="GEMINI_API_KEY",
        model_hint="Gemini 3 Pro Preview 已关闭，官方建议迁移到 3.1 Pro Preview；稳定默认使用 3.5 Flash。",
        docs_url="https://ai.google.dev/gemini-api/docs/openai",
    ),
    ProviderSpec(
        "zhipu",
        ("zhipu", "glm", "zai"),
        "ZAI_API_KEY",
        display_name="Zhipu AI",
        env_extras=(("ZHIPUAI_API_KEY", "{api_key}"),),
        default_api_base="https://open.bigmodel.cn/api/paas/v4",
        default_model="glm-5.1",
        model_options=("glm-5.1", "glm-5", "glm-5-turbo", "glm-4.7", "glm-4.6", "glm-4.5"),
        credential_hint="ZAI_API_KEY / ZHIPUAI_API_KEY",
        model_hint="GLM-5.1 面向长程 Agent 与复杂任务，GLM-5-Turbo 更适合成本敏感场景。",
        docs_url="https://docs.bigmodel.cn/cn/guide/models/text/glm-5.1",
    ),
    ProviderSpec(
        "dashscope",
        ("qwen", "dashscope"),
        "DASHSCOPE_API_KEY",
        display_name="DashScope",
        default_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model="qwen3.6-plus",
        model_options=(
            "qwen3.6-plus",
            "qwen3.6-flash",
            "qwen3.6-max-preview",
            "qwen3-max",
            "qwen3.5-plus",
            "qwen3.5-flash",
            "qwen3-coder-plus",
            "qwen3-coder-flash",
            "qwen3-next-80b-a3b-thinking",
        ),
        credential_hint="DASHSCOPE_API_KEY",
        model_hint="教育问答默认 Plus；高质量可选 Max Preview；低延迟可选 Flash。",
        docs_url="https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope",
    ),
    ProviderSpec(
        "iflytek_spark_ws",
        (
            "iflytek",
            "xfyun",
            "xunfei",
            "spark",
            "websocket",
            "spark-x",
            "spark-x2",
            "spark-x1.5",
        ),
        "IFLYTEK_SPARK_API_KEY",
        display_name="iFlytek Spark X",
        backend="openai_compat",
        is_direct=True,
        detect_by_base_keyword="spark-api-open.xf-yun",
        default_api_base=IFLYTEK_SPARK_X2_BASE_URL,
        default_model=IFLYTEK_SPARK_MODEL,
        model_options=(IFLYTEK_SPARK_MODEL,),
        credential_hint="IFLYTEK_APPID + IFLYTEK_API_KEY + IFLYTEK_API_SECRET，或 APIPassword",
        model_hint="X2 与 X1.5 的模型名均为 spark-x，通过服务地址区分版本。",
        docs_url="https://www.xfyun.cn/doc/spark/X1http.html",
    ),
    ProviderSpec(
        "iflytek_maas_coding",
        (
            "iflytek_maas",
            "xfyun_maas",
            "xunfei_maas",
            "maas-coding",
            "maas_coding",
            "astron",
            "astron-code",
            "astron_code",
        ),
        "IFLYTEK_MAAS_API_PASSWORD",
        display_name="iFlytek MaaS Coding",
        is_direct=True,
        detect_by_base_keyword="maas-coding-api.cn-huabei-1.xf-yun.com",
        default_api_base=IFLYTEK_MAAS_CODING_BASE_URL,
        default_model=IFLYTEK_MAAS_CODING_MODEL,
        model_options=(IFLYTEK_MAAS_CODING_MODEL,),
        credential_hint="IFLYTEK_MAAS_API_PASSWORD（MaaS APIPassword，形如 APIKey:APISecret）",
        model_hint=(
            "Astron Code 适合代码智能体、工具编排和工程化生成；"
            f"OpenAI-compatible 使用 {IFLYTEK_MAAS_CODING_BASE_URL}，"
            f"Anthropic-compatible 入口可作为自定义端点使用 {IFLYTEK_MAAS_CODING_ANTHROPIC_URL}。"
        ),
        docs_url="https://maas.xfyun.cn/",
    ),
    ProviderSpec(
        "moonshot",
        ("moonshot", "kimi"),
        "MOONSHOT_API_KEY",
        display_name="Moonshot",
        default_api_base="https://api.moonshot.cn/v1",
        default_model="kimi-k2.5",
        model_options=(
            "kimi-k2.5",
            "kimi-k2-thinking",
            "kimi-k2-thinking-turbo",
            "kimi-k2-0905-Preview",
            "kimi-k2-turbo-preview",
            "moonshot-v1-128k",
            "moonshot-v1-32k",
        ),
        model_overrides=(("kimi-k2.5", {"temperature": 1.0}),),
        credential_hint="MOONSHOT_API_KEY",
        model_hint="Kimi K2.5 系列支持 256K 上下文，适合长资料理解和 Agent 任务。",
        docs_url="https://platform.moonshot.cn/docs/guide/kimi-k2-5-quickstart",
    ),
    ProviderSpec(
        "minimax",
        ("minimax",),
        "MINIMAX_API_KEY",
        display_name="MiniMax",
        default_api_base="https://api.minimax.io/v1",
        default_model="MiniMax-M2.7",
        model_options=("MiniMax-M2.7", "MiniMax-M2.7-highspeed", "MiniMax-M2.5"),
        credential_hint="MINIMAX_API_KEY",
        model_hint="M2.7 面向复杂生产力和 Agent 任务，M2.5 可作为兼容备选。",
        docs_url="https://www.minimax.io/models/text/m27",
    ),
    ProviderSpec(
        "mistral",
        ("mistral",),
        "MISTRAL_API_KEY",
        display_name="Mistral",
        default_api_base="https://api.mistral.ai/v1",
        default_model="mistral-large-2512",
        model_options=(
            "mistral-large-2512",
            "mistral-small-2603",
            "magistral-medium-2509",
            "ministral-14b-2512",
            "ministral-8b-2512",
        ),
        credential_hint="MISTRAL_API_KEY",
        model_hint="Large 3 适合高质量多模态，Small 4 更适合低延迟任务。",
        docs_url="https://docs.mistral.ai/models/overview",
    ),
    ProviderSpec(
        "stepfun",
        ("stepfun", "step"),
        "STEPFUN_API_KEY",
        display_name="Step Fun",
        default_api_base="https://api.stepfun.com/v1",
        default_model="step-3.5-flash",
        model_options=("step-3.5-flash", "step-2-16k", "step-1-32k"),
    ),
    ProviderSpec(
        "xiaomi_mimo",
        ("xiaomi_mimo", "mimo"),
        "XIAOMIMIMO_API_KEY",
        display_name="Xiaomi MIMO",
        default_api_base="https://api.xiaomimimo.com/v1",
        default_model="MiMo-VL-7B-RL",
        model_options=("MiMo-VL-7B-RL", "MiMo-7B-RL"),
    ),
    ProviderSpec(
        "vllm",
        ("vllm",),
        "HOSTED_VLLM_API_KEY",
        display_name="vLLM",
        is_local=True,
        default_api_base="http://localhost:8000/v1",
    ),
    ProviderSpec(
        "ollama",
        ("ollama", "nemotron"),
        "OLLAMA_API_KEY",
        display_name="Ollama",
        is_local=True,
        detect_by_base_keyword="11434",
        default_api_base="http://localhost:11434/v1",
    ),
    ProviderSpec(
        "lm_studio",
        ("lmstudio", "lm_studio"),
        "",
        display_name="LM Studio",
        is_local=True,
        detect_by_base_keyword="1234",
        default_api_base="http://localhost:1234/v1",
    ),
    ProviderSpec(
        "llama_cpp",
        ("llama_cpp", "llama.cpp"),
        "",
        display_name="llama.cpp",
        is_local=True,
        detect_by_base_keyword="8080",
        default_api_base="http://localhost:8080/v1",
    ),
    ProviderSpec(
        "ovms",
        ("openvino", "ovms"),
        "",
        display_name="OpenVINO Model Server",
        is_direct=True,
        is_local=True,
        default_api_base="http://localhost:8000/v3",
    ),
    ProviderSpec(
        "groq",
        ("groq",),
        "GROQ_API_KEY",
        display_name="Groq",
        default_api_base="https://api.groq.com/openai/v1",
        default_model="openai/gpt-oss-120b",
        model_options=(
            "openai/gpt-oss-120b",
            "llama-3.1-8b-instant",
            "meta-llama/llama-4-scout-17b-16e-instruct",
        ),
    ),
    ProviderSpec(
        "qianfan",
        ("qianfan", "ernie"),
        "QIANFAN_API_KEY",
        display_name="Qianfan",
        default_api_base="https://qianfan.baidubce.com/v2",
        default_model="ernie-4.5-turbo-128k",
        model_options=("ernie-4.5-turbo-128k", "ernie-x1-turbo-32k", "ernie-4.0-turbo-8k"),
    ),
)

NANOBOT_LLM_PROVIDERS: tuple[str, ...] = tuple(spec.name for spec in PROVIDERS)

SUPPORTED_SEARCH_PROVIDERS = {
    "brave",
    "tavily",
    "jina",
    "searxng",
    "duckduckgo",
    "perplexity",
    "serper",
    "iflytek_spark",
}
DEPRECATED_SEARCH_PROVIDERS = {"exa", "baidu", "openrouter"}
SEARCH_ENV_FALLBACK = {
    "brave": ("BRAVE_API_KEY",),
    "tavily": ("TAVILY_API_KEY",),
    "jina": ("JINA_API_KEY",),
    "perplexity": ("PERPLEXITY_API_KEY",),
    "serper": ("SERPER_API_KEY",),
    "iflytek_spark": (
        "IFLYTEK_API_PASSWORD",
        "IFLYTEK_SEARCH_API_PASSWORD",
        "IFLYTEK_SPARK_SEARCH_API_PASSWORD",
        "XFYUN_SEARCH_API_PASSWORD",
        "IFLYTEK_SEARCH_APIPASSWORD",
    ),
}

EMBEDDING_PROVIDER_ALIASES = {
    "google": "openai",
    "gemini": "openai",
    "iflytek": "iflytek_spark",
    "xfyun": "iflytek_spark",
    "xunfei": "iflytek_spark",
    "spark": "iflytek_spark",
    "spark_embedding": "iflytek_spark",
    "iflytek_embedding": "iflytek_spark",
    "xfyun_embedding": "iflytek_spark",
    "xunfei_embedding": "iflytek_spark",
    "huggingface": "custom",
    "lm_studio": "vllm",
    "llama_cpp": "vllm",
    "openai_compatible": "custom",
}


@dataclass(frozen=True)
class EmbeddingProviderSpec:
    """Single embedding-provider metadata entry."""

    label: str
    default_api_base: str
    keywords: tuple[str, ...]
    is_local: bool
    api_key_envs: tuple[str, ...]
    adapter: str = "openai_compat"
    mode: str = "standard"
    default_model: str = ""
    default_dim: int = 0
    model_options: tuple[str, ...] = ()
    credential_hint: str = ""
    model_hint: str = ""
    docs_url: str = ""


EMBEDDING_PROVIDERS: dict[str, EmbeddingProviderSpec] = {
    "openai": EmbeddingProviderSpec(
        label="OpenAI",
        default_api_base="https://api.openai.com/v1",
        keywords=("openai", "text-embedding", "ada-002", "embedding-3"),
        is_local=False,
        api_key_envs=("OPENAI_API_KEY",),
        default_model="text-embedding-3-large",
        default_dim=3072,
        model_options=("text-embedding-3-large", "text-embedding-3-small"),
        credential_hint="OPENAI_API_KEY",
        model_hint="3-large 质量更高，3-small 更省成本。",
        docs_url="https://platform.openai.com/docs/guides/embeddings",
    ),
    "azure_openai": EmbeddingProviderSpec(
        label="Azure OpenAI",
        mode="direct",
        default_api_base="",
        keywords=("azure", "aoai"),
        is_local=False,
        api_key_envs=("AZURE_OPENAI_API_KEY", "AZURE_API_KEY"),
        credential_hint="AZURE_OPENAI_API_KEY",
        model_hint="模型名通常填写 Azure deployment name。",
        docs_url="https://learn.microsoft.com/azure/ai-services/openai/reference",
    ),
    "cohere": EmbeddingProviderSpec(
        label="Cohere",
        adapter="cohere",
        default_api_base="https://api.cohere.ai",
        keywords=("cohere", "embed-v4", "embed-english", "embed-multilingual"),
        is_local=False,
        api_key_envs=("COHERE_API_KEY",),
        default_model="embed-v4.0",
        default_dim=1024,
        model_options=("embed-v4.0", "embed-english-v3.0", "embed-multilingual-v3.0"),
        credential_hint="COHERE_API_KEY",
        model_hint="embed-v4.0 同时支持文本和图像；多语言资料也可使用 multilingual v3。",
        docs_url="https://docs.cohere.com/docs/cohere-embed",
    ),
    "jina": EmbeddingProviderSpec(
        label="Jina",
        adapter="jina",
        default_api_base="https://api.jina.ai/v1",
        keywords=("jina", "jina-embeddings"),
        is_local=False,
        api_key_envs=("JINA_API_KEY",),
        default_model="jina-embeddings-v3",
        default_dim=1024,
        model_options=("jina-embeddings-v3", "jina-clip-v2"),
        credential_hint="JINA_API_KEY",
        model_hint="jina-embeddings-v3 适合通用文本检索；CLIP 模型适合多模态资料。",
        docs_url="https://jina.ai/embeddings/",
    ),
    "siliconflow": EmbeddingProviderSpec(
        label="SiliconFlow",
        default_api_base="https://api.siliconflow.cn/v1",
        keywords=("siliconflow", "qwen3-embedding", "qwen/qwen3-embedding"),
        is_local=False,
        api_key_envs=("SILICONFLOW_API_KEY",),
        default_model="Qwen/Qwen3-Embedding-8B",
        default_dim=4096,
        model_options=(
            "Qwen/Qwen3-Embedding-8B",
            "BAAI/bge-m3",
            "netease-youdao/bce-embedding-base_v1",
        ),
        credential_hint="SILICONFLOW_API_KEY",
        model_hint="Qwen3 Embedding 适合中文高校课程资料；切换模型后需重建知识库索引。",
        docs_url="https://docs.siliconflow.cn/cn/api-reference/embeddings/create-embeddings",
    ),
    "iflytek_spark": EmbeddingProviderSpec(
        label="iFlytek Spark Embedding",
        adapter="iflytek_spark",
        default_api_base="https://emb-cn-huabei-1.xf-yun.com/",
        keywords=("iflytek", "xfyun", "xunfei", "llm-embedding"),
        is_local=False,
        api_key_envs=(
            "IFLYTEK_API_KEY",
            "IFLYTEK_EMBEDDING_API_KEY",
            "IFLYTEK_SPARK_EMBEDDING_API_KEY",
            "IFLYTEK_OCR_API_KEY",
            "IFLYTEK_TTS_API_KEY",
            "XFYUN_EMBEDDING_API_KEY",
            "SPARK_EMBEDDING_API_KEY",
        ),
        default_model="llm-embedding",
        default_dim=2560,
        model_options=("llm-embedding",),
        credential_hint="IFLYTEK_APPID + IFLYTEK_API_KEY + IFLYTEK_API_SECRET",
        model_hint="讯飞 llm-embedding 固定 2560 维，domain 可在 para/query 间切换。",
        docs_url="https://www.xfyun.cn/doc/spark/Embedding_api.html",
    ),
    "ollama": EmbeddingProviderSpec(
        label="Ollama",
        adapter="ollama",
        mode="local",
        default_api_base="http://localhost:11434",
        keywords=("ollama", "nomic-embed", "mxbai", "snowflake-arctic", "all-minilm"),
        is_local=True,
        api_key_envs=(),
        default_model="nomic-embed-text",
        default_dim=768,
        model_options=("nomic-embed-text", "mxbai-embed-large", "snowflake-arctic-embed"),
        credential_hint="本地服务无需密钥",
        model_hint="容器内访问宿主机 Ollama 时，地址通常要写 host.docker.internal。",
        docs_url="https://ollama.com/blog/embedding-models",
    ),
    "vllm": EmbeddingProviderSpec(
        label="vLLM / LM Studio",
        mode="local",
        default_api_base="http://localhost:8000/v1",
        keywords=("vllm", "lmstudio"),
        is_local=True,
        api_key_envs=("HOSTED_VLLM_API_KEY",),
        credential_hint="本地服务可留空，托管服务填写 HOSTED_VLLM_API_KEY",
        model_hint="填写本地 OpenAI-compatible embedding 模型名。",
    ),
    "custom": EmbeddingProviderSpec(
        label="OpenAI Compatible",
        mode="direct",
        default_api_base="",
        keywords=(),
        is_local=False,
        api_key_envs=("OPENAI_API_KEY",),
        credential_hint="按兼容服务要求填写 API Key",
        model_hint="用于任何 OpenAI-compatible embedding endpoint。",
    ),
}


def canonical_provider_name(name: str | None) -> str | None:
    """Normalize incoming provider names and legacy aliases."""
    if not name:
        return None
    key = name.strip()
    if not key:
        return None
    key = key.replace("-", "_")
    return PROVIDER_ALIASES.get(key, key)


def find_by_name(name: str | None) -> ProviderSpec | None:
    canonical = canonical_provider_name(name)
    if not canonical:
        return None
    for spec in PROVIDERS:
        if spec.name == canonical:
            return spec
    return None


def find_by_model(model: str | None) -> ProviderSpec | None:
    if not model:
        return None
    model_lower = model.lower()
    model_normalized = model_lower.replace("-", "_")
    model_prefix = model_lower.split("/", 1)[0] if "/" in model_lower else ""
    normalized_prefix = model_prefix.replace("-", "_")
    standard_specs = [s for s in PROVIDERS if not s.is_gateway and not s.is_local]

    for spec in standard_specs:
        if model_prefix and normalized_prefix == spec.name:
            return spec
    for spec in standard_specs:
        if any(
            kw in model_lower or kw.replace("-", "_") in model_normalized for kw in spec.keywords
        ):
            return spec
    return None


def find_gateway(
    provider_name: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
) -> ProviderSpec | None:
    spec = find_by_name(provider_name)
    if spec and (spec.is_gateway or spec.is_local):
        return spec

    for item in PROVIDERS:
        if item.detect_by_key_prefix and api_key and api_key.startswith(item.detect_by_key_prefix):
            return item
        if item.detect_by_base_keyword and api_base and item.detect_by_base_keyword in api_base:
            return item
    return None


def strip_provider_prefix(model: str, spec: ProviderSpec | None) -> str:
    """Strip provider/model prefixes for gateways that expect bare model names."""
    if not model or not spec:
        return model
    if spec.strip_model_prefix and "/" in model:
        return model.split("/", 1)[1]
    return model


__all__ = [
    "DEPRECATED_SEARCH_PROVIDERS",
    "EMBEDDING_PROVIDERS",
    "EMBEDDING_PROVIDER_ALIASES",
    "EmbeddingProviderSpec",
    "IFLYTEK_MAAS_CODING_ANTHROPIC_URL",
    "IFLYTEK_MAAS_CODING_BASE_URL",
    "IFLYTEK_MAAS_CODING_MODEL",
    "IFLYTEK_SPARK_MODEL",
    "IFLYTEK_SPARK_X15_BASE_URL",
    "IFLYTEK_SPARK_X2_BASE_URL",
    "NANOBOT_LLM_PROVIDERS",
    "PROVIDER_ALIASES",
    "PROVIDERS",
    "ProviderSpec",
    "SEARCH_ENV_FALLBACK",
    "SUPPORTED_SEARCH_PROVIDERS",
    "canonical_provider_name",
    "find_by_model",
    "find_by_name",
    "find_gateway",
    "strip_provider_prefix",
]
