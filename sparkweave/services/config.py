"""NG-owned LLM configuration resolution.

This module reads the same user-facing configuration files as the legacy
runtime, but it does not import from the legacy package. The goal is to keep
LangGraph services runnable after the old package becomes a compatibility
shim or is removed.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field, replace
import json
import logging
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterable, TypedDict
from urllib.parse import urlparse
from uuid import uuid4

import yaml

from sparkweave.services.paths import get_path_service

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"
IFLYTEK_SPARK_MODEL = "spark-x"
IFLYTEK_SPARK_X2_BASE_URL = "https://spark-api-open.xf-yun.com/x2/"
IFLYTEK_SPARK_X15_BASE_URL = "https://spark-api-open.xf-yun.com/v2/"
IFLYTEK_MAAS_CODING_MODEL = "astron-code-latest"
IFLYTEK_MAAS_CODING_BASE_URL = "https://maas-coding-api.cn-huabei-1.xf-yun.com/v2"
IFLYTEK_MAAS_CODING_ANTHROPIC_URL = "https://maas-coding-api.cn-huabei-1.xf-yun.com/anthropic"


class LLMConfigError(RuntimeError):
    """Raised when no usable LLM configuration can be resolved."""


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
        model_options=("gpt-5.5", "gpt-5.4-mini", "claude-opus-4-7", "gemini-3.5-flash", "deepseek-v4-flash"),
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
        model_options=("gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.2", "gpt-4.1", "gpt-4.1-mini"),
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
        model_options=("deepseek-v4-flash", "deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner"),
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
        model_options=("openai/gpt-oss-120b", "llama-3.1-8b-instant", "meta-llama/llama-4-scout-17b-16e-instruct"),
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
        model_options=("Qwen/Qwen3-Embedding-8B", "BAAI/bge-m3", "netease-youdao/bce-embedding-base_v1"),
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
            kw in model_lower or kw.replace("-", "_") in model_normalized
            for kw in spec.keywords
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


DEFAULT_IFLYTEK_OCR_URL = "https://cbm01.cn-huabei-1.xf-yun.com/v1/private/se75ocrbm"
DEFAULT_IFLYTEK_OCR_SERVICE_ID = "se75ocrbm"
DEFAULT_IFLYTEK_OCR_CATEGORY = "ch_en_public_cloud"
DEFAULT_SILICONFLOW_OCR_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_SILICONFLOW_OCR_MODEL = "deepseek-ai/DeepSeek-OCR"
DEFAULT_SILICONFLOW_OCR_PROMPT = "<image>\n<|grounding|>Convert the document to markdown."
DEFAULT_OCR_TIMEOUT = "90"
DEFAULT_OCR_MAX_PAGES = ""
DEFAULT_OCR_DPI = "200"
DEFAULT_OCR_MIN_TEXT_CHARS = "40"
DEFAULT_SILICONFLOW_OCR_MAX_TOKENS = "8192"
DEFAULT_IFLYTEK_TTS_URL = "wss://cbm01.cn-huabei-1.xf-yun.com/v1/private/mcd9m97e6"
DEFAULT_IFLYTEK_TTS_VOICE = "x5_lingxiaoxuan_flow"
DEFAULT_IFLYTEK_ASR_URL = "wss://iat-api.xfyun.cn/v2/iat"
DEFAULT_IFLYTEK_SPEECH_EVAL_URL = "wss://ise-api.xfyun.cn/v2/open-ise"
DEFAULT_IFLYTEK_FORMULA_URL = "https://rest-api.xfyun.cn/v2/itr"
DEFAULT_IFLYTEK_FORMULA_ENT = "teach-photo-print"
DEFAULT_IFLYTEK_FORMULA_AUE = "raw"
DEFAULT_IFLYTEK_VISION_URL = "wss://spark-api.cn-huabei-1.xf-yun.com/v2.1/image"
DEFAULT_IFLYTEK_VISION_PROTOCOL = "spark_image"
DEFAULT_IFLYTEK_VISION_DOMAIN = "imagev3"


ENV_KEY_ORDER = (
    "BACKEND_PORT",
    "FRONTEND_PORT",
    "IFLYTEK_APPID",
    "IFLYTEK_API_KEY",
    "IFLYTEK_API_SECRET",
    "IFLYTEK_API_PASSWORD",
    "IFLYTEK_MAAS_API_PASSWORD",
    "SILICONFLOW_API_KEY",
    "LLM_BINDING",
    "LLM_MODEL",
    "LLM_API_KEY",
    "LLM_HOST",
    "LLM_API_VERSION",
    "EMBEDDING_BINDING",
    "EMBEDDING_MODEL",
    "EMBEDDING_API_KEY",
    "EMBEDDING_HOST",
    "EMBEDDING_DIMENSION",
    "EMBEDDING_API_VERSION",
    "SEARCH_PROVIDER",
    "SEARCH_API_KEY",
    "SEARCH_BASE_URL",
    "SEARCH_PROXY",
    "SPARKWEAVE_OCR_PROVIDER",
    "SPARKWEAVE_PDF_OCR_STRATEGY",
    "SPARKWEAVE_OCR_TIMEOUT",
    "SPARKWEAVE_OCR_MAX_PAGES",
    "SPARKWEAVE_OCR_DPI",
    "SPARKWEAVE_OCR_MIN_TEXT_CHARS",
    "IFLYTEK_OCR_APPID",
    "IFLYTEK_OCR_API_KEY",
    "IFLYTEK_OCR_API_SECRET",
    "IFLYTEK_OCR_URL",
    "IFLYTEK_OCR_SERVICE_ID",
    "IFLYTEK_OCR_CATEGORY",
    "SILICONFLOW_OCR_API_KEY",
    "SILICONFLOW_OCR_BASE_URL",
    "SILICONFLOW_OCR_MODEL",
    "SILICONFLOW_OCR_PROMPT",
    "SPARKWEAVE_TTS_PROVIDER",
    "SPARKWEAVE_TTS_TIMEOUT",
    "IFLYTEK_TTS_APPID",
    "IFLYTEK_TTS_API_KEY",
    "IFLYTEK_TTS_API_SECRET",
    "IFLYTEK_TTS_URL",
    "IFLYTEK_TTS_VOICE",
    "IFLYTEK_TTS_ENCODING",
    "IFLYTEK_TTS_SAMPLE_RATE",
    "IFLYTEK_TTS_CHANNELS",
    "IFLYTEK_TTS_BIT_DEPTH",
    "IFLYTEK_TTS_FRAME_SIZE",
    "IFLYTEK_TTS_SPEED",
    "IFLYTEK_TTS_VOLUME",
    "IFLYTEK_TTS_PITCH",
    "SPARKWEAVE_ASR_PROVIDER",
    "SPARKWEAVE_ASR_TIMEOUT",
    "IFLYTEK_ASR_APPID",
    "IFLYTEK_ASR_API_KEY",
    "IFLYTEK_ASR_API_SECRET",
    "IFLYTEK_ASR_URL",
    "IFLYTEK_ASR_LANGUAGE",
    "IFLYTEK_ASR_ACCENT",
    "IFLYTEK_ASR_DOMAIN",
    "IFLYTEK_ASR_VAD_EOS",
    "SPARKWEAVE_SPEECH_EVAL_PROVIDER",
    "SPARKWEAVE_SPEECH_EVAL_TIMEOUT",
    "IFLYTEK_SPEECH_EVAL_APPID",
    "IFLYTEK_SPEECH_EVAL_API_KEY",
    "IFLYTEK_SPEECH_EVAL_API_SECRET",
    "IFLYTEK_SPEECH_EVAL_URL",
    "IFLYTEK_SPEECH_EVAL_CATEGORY",
    "IFLYTEK_SPEECH_EVAL_LANGUAGE",
    "SPARKWEAVE_FORMULA_OCR_PROVIDER",
    "IFLYTEK_FORMULA_URL",
    "IFLYTEK_FORMULA_APPID",
    "IFLYTEK_FORMULA_API_KEY",
    "IFLYTEK_FORMULA_API_SECRET",
    "IFLYTEK_FORMULA_ENT",
    "IFLYTEK_FORMULA_AUE",
    "IFLYTEK_FORMULA_TIMEOUT",
    "SPARKWEAVE_IMAGE_UNDERSTANDING_PROVIDER",
    "IFLYTEK_VISION_PROTOCOL",
    "IFLYTEK_VISION_URL",
    "IFLYTEK_VISION_APPID",
    "IFLYTEK_VISION_API_KEY",
    "IFLYTEK_VISION_API_SECRET",
    "IFLYTEK_VISION_DOMAIN",
    "IFLYTEK_VISION_MAX_TOKENS",
    "IFLYTEK_VISION_TEMPERATURE",
    "IFLYTEK_VISION_TOP_K",
    "IFLYTEK_VISION_TIMEOUT",
    "IFLYTEK_VISION_UID",
    "SPARKWEAVE_IFLYTEK_OFFLINE_FALLBACK",
    "SPARKWEAVE_OFFLINE_ASR_TEXT",
)


def _parse_env_lines(lines: Iterable[str]) -> OrderedDict[str, str]:
    values: OrderedDict[str, str] = OrderedDict()
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def _safe_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


@dataclass(slots=True)
class ConfigSummary:
    backend_port: int
    frontend_port: int
    llm: dict[str, str]
    embedding: dict[str, str]
    search: dict[str, str]
    ocr: dict[str, str]
    tts: dict[str, str]
    asr: dict[str, str]
    speech_eval: dict[str, str]


class EnvStore:
    """Small `.env` reader compatible with the existing SparkWeave layout."""

    def __init__(self, path: Path = ENV_PATH):
        self.path = path

    def _include_process_env(self) -> bool:
        try:
            return self.path.resolve() == ENV_PATH.resolve()
        except Exception:
            return self.path == ENV_PATH

    def load(self) -> OrderedDict[str, str]:
        if self.path.exists():
            values = _parse_env_lines(self.path.read_text(encoding="utf-8").splitlines())
        else:
            values = OrderedDict()
        if self._include_process_env():
            for key, value in values.items():
                os.environ.setdefault(key, value)
        return values

    def get(self, key: str, default: str = "") -> str:
        values = self.load()
        file_value = values.get(key)
        if file_value not in (None, ""):
            return file_value
        process_value = os.getenv(key) if self._include_process_env() else None
        if process_value not in (None, ""):
            return process_value
        return default

    def as_summary(self) -> ConfigSummary:
        values = self.load()
        include_process_env = self._include_process_env()
        def value(key: str, default: str = "") -> str:
            file_value = values.get(key)
            if file_value not in (None, ""):
                return _as_str(file_value)
            process_value = os.getenv(key) if include_process_env else ""
            return _as_str(process_value or default)

        iflytek_app_id = value("IFLYTEK_APPID")
        iflytek_api_key = value("IFLYTEK_API_KEY")
        iflytek_api_secret = value("IFLYTEK_API_SECRET")
        iflytek_api_password = value("IFLYTEK_API_PASSWORD")
        if not iflytek_api_password and iflytek_api_key and iflytek_api_secret:
            iflytek_api_password = f"{iflytek_api_key}:{iflytek_api_secret}"
        siliconflow_api_key = value("SILICONFLOW_API_KEY")

        llm_binding = value("LLM_BINDING", "openai")
        llm_host = value("LLM_HOST")
        llm_api_key = value("LLM_API_KEY")
        if not llm_api_key:
            llm_provider = canonical_provider_name(llm_binding)
            if llm_provider == "iflytek_spark_ws":
                llm_api_key = iflytek_api_password or iflytek_api_key
            elif llm_provider == "iflytek_maas_coding":
                llm_api_key = value("IFLYTEK_MAAS_API_PASSWORD") or value("IFLYTEK_MAAS_CODING_API_PASSWORD")
            elif llm_provider == "siliconflow" or "siliconflow" in llm_host.lower():
                llm_api_key = siliconflow_api_key

        embedding_binding = value("EMBEDDING_BINDING", "openai")
        embedding_host = value("EMBEDDING_HOST")
        embedding_api_key = value("EMBEDDING_API_KEY")
        if not embedding_api_key:
            embedding_provider = _canonical_embedding_provider_name(embedding_binding)
            if embedding_provider == "iflytek_spark":
                embedding_api_key = iflytek_api_key
            elif embedding_binding == "siliconflow" or "siliconflow" in embedding_host.lower():
                embedding_api_key = siliconflow_api_key

        search_provider = value("SEARCH_PROVIDER")
        search_api_key = value("SEARCH_API_KEY")
        if not search_api_key and search_provider.strip().lower().replace("-", "_") == "iflytek_spark":
            search_api_key = iflytek_api_password or iflytek_api_key

        ocr_provider = value("SPARKWEAVE_OCR_PROVIDER", "iflytek")
        ocr_is_siliconflow = ocr_provider.strip().lower().replace("-", "_") in {
            "siliconflow",
            "silicon_flow",
            "deepseekocr",
            "deepseek_ocr",
        }
        return ConfigSummary(
            backend_port=_safe_int(value("BACKEND_PORT"), 8001),
            frontend_port=_safe_int(value("FRONTEND_PORT"), 3782),
            llm={
                "binding": llm_binding,
                "model": value("LLM_MODEL"),
                "api_key": llm_api_key,
                "host": llm_host,
                "api_version": value("LLM_API_VERSION"),
            },
            embedding={
                "binding": embedding_binding,
                "model": value("EMBEDDING_MODEL"),
                "api_key": embedding_api_key,
                "host": embedding_host,
                "dimension": value("EMBEDDING_DIMENSION", "3072"),
                "api_version": value("EMBEDDING_API_VERSION"),
            },
            search={
                "provider": search_provider,
                "api_key": search_api_key,
                "base_url": value("SEARCH_BASE_URL"),
                "proxy": value("SEARCH_PROXY"),
            },
            ocr={
                "provider": ocr_provider,
                "strategy": value("SPARKWEAVE_PDF_OCR_STRATEGY", "auto"),
                "timeout": value("SPARKWEAVE_OCR_TIMEOUT"),
                "max_pages": value("SPARKWEAVE_OCR_MAX_PAGES"),
                "dpi": value("SPARKWEAVE_OCR_DPI"),
                "min_text_chars": value("SPARKWEAVE_OCR_MIN_TEXT_CHARS"),
                "app_id": value("IFLYTEK_OCR_APPID") or iflytek_app_id,
                "api_key": (value("SILICONFLOW_OCR_API_KEY") or siliconflow_api_key)
                if ocr_is_siliconflow
                else (value("IFLYTEK_OCR_API_KEY") or iflytek_api_key),
                "api_secret": value("IFLYTEK_OCR_API_SECRET") or iflytek_api_secret,
                "url": value("IFLYTEK_OCR_URL", DEFAULT_IFLYTEK_OCR_URL),
                "service_id": value("IFLYTEK_OCR_SERVICE_ID", DEFAULT_IFLYTEK_OCR_SERVICE_ID),
                "category": value("IFLYTEK_OCR_CATEGORY", DEFAULT_IFLYTEK_OCR_CATEGORY),
                "siliconflow_api_key": value("SILICONFLOW_OCR_API_KEY") or siliconflow_api_key,
                "siliconflow_base_url": value("SILICONFLOW_OCR_BASE_URL", DEFAULT_SILICONFLOW_OCR_BASE_URL),
                "siliconflow_model": value("SILICONFLOW_OCR_MODEL", DEFAULT_SILICONFLOW_OCR_MODEL),
                "siliconflow_prompt": value("SILICONFLOW_OCR_PROMPT", DEFAULT_SILICONFLOW_OCR_PROMPT),
            },
            tts={
                "provider": value("SPARKWEAVE_TTS_PROVIDER", "iflytek"),
                "timeout": value("SPARKWEAVE_TTS_TIMEOUT", "30"),
                "app_id": value("IFLYTEK_TTS_APPID") or iflytek_app_id,
                "api_key": value("IFLYTEK_TTS_API_KEY") or iflytek_api_key,
                "api_secret": value("IFLYTEK_TTS_API_SECRET") or iflytek_api_secret,
                "url": value("IFLYTEK_TTS_URL", DEFAULT_IFLYTEK_TTS_URL),
                "voice": value("IFLYTEK_TTS_VOICE", DEFAULT_IFLYTEK_TTS_VOICE),
                "encoding": value("IFLYTEK_TTS_ENCODING", "lame"),
                "sample_rate": value("IFLYTEK_TTS_SAMPLE_RATE", "24000"),
                "channels": value("IFLYTEK_TTS_CHANNELS", "1"),
                "bit_depth": value("IFLYTEK_TTS_BIT_DEPTH", "16"),
                "frame_size": value("IFLYTEK_TTS_FRAME_SIZE", "0"),
                "speed": value("IFLYTEK_TTS_SPEED", "50"),
                "volume": value("IFLYTEK_TTS_VOLUME", "50"),
                "pitch": value("IFLYTEK_TTS_PITCH", "50"),
            },
            asr={
                "provider": value("SPARKWEAVE_ASR_PROVIDER", "iflytek"),
                "timeout": value("SPARKWEAVE_ASR_TIMEOUT", "60"),
                "app_id": value("IFLYTEK_ASR_APPID") or iflytek_app_id,
                "api_key": value("IFLYTEK_ASR_API_KEY") or iflytek_api_key,
                "api_secret": value("IFLYTEK_ASR_API_SECRET") or iflytek_api_secret,
                "url": value("IFLYTEK_ASR_URL", DEFAULT_IFLYTEK_ASR_URL),
                "language": value("IFLYTEK_ASR_LANGUAGE", "zh_cn"),
                "accent": value("IFLYTEK_ASR_ACCENT", "mandarin"),
                "domain": value("IFLYTEK_ASR_DOMAIN", "iat"),
                "vad_eos": value("IFLYTEK_ASR_VAD_EOS", "3000"),
            },
            speech_eval={
                "provider": value("SPARKWEAVE_SPEECH_EVAL_PROVIDER", "iflytek"),
                "timeout": value("SPARKWEAVE_SPEECH_EVAL_TIMEOUT", "60"),
                "app_id": value("IFLYTEK_SPEECH_EVAL_APPID") or iflytek_app_id,
                "api_key": value("IFLYTEK_SPEECH_EVAL_API_KEY") or iflytek_api_key,
                "api_secret": value("IFLYTEK_SPEECH_EVAL_API_SECRET") or iflytek_api_secret,
                "url": value("IFLYTEK_SPEECH_EVAL_URL", DEFAULT_IFLYTEK_SPEECH_EVAL_URL),
                "category": value("IFLYTEK_SPEECH_EVAL_CATEGORY", "read_sentence"),
                "language": value("IFLYTEK_SPEECH_EVAL_LANGUAGE", "zh_cn"),
            },
        )

    def write(self, values: dict[str, str]) -> None:
        """Atomically write runtime env values while preserving known key order."""
        current = self.load()
        current.update({key: value for key, value in values.items() if value is not None})
        ordered: OrderedDict[str, str] = OrderedDict()
        for key in ENV_KEY_ORDER:
            value = current.get(key, "")
            if key == "SEARCH_BASE_URL" and not value:
                continue
            ordered[key] = value

        rendered = "\n".join(f"{key}={value}" for key, value in ordered.items()) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(self.path.parent),
            delete=False,
        ) as handle:
            handle.write(rendered)
            tmp_path = Path(handle.name)
        tmp_path.replace(self.path)
        for key, value in ordered.items():
            os.environ[key] = value

    def render_from_catalog(self, catalog: dict[str, Any]) -> dict[str, str]:
        """Render active catalog selections to legacy-compatible env keys."""
        services = catalog.get("services", {})
        llm_service = services.get("llm", {})
        embedding_service = services.get("embedding", {})
        search_service = services.get("search", {})
        ocr_service = services.get("ocr", {})
        formula_ocr_service = services.get("formula_ocr", {})
        image_understanding_service = services.get("image_understanding", {})
        tts_service = services.get("tts", {})
        asr_service = services.get("asr", {})
        speech_eval_service = services.get("speech_eval", {})

        llm_profile = self._get_active_profile(llm_service)
        llm_model = self._get_active_model(llm_service, llm_profile)
        embedding_profile = self._get_active_profile(embedding_service)
        embedding_model = self._get_active_model(embedding_service, embedding_profile)
        search_profile = self._get_active_profile(search_service)
        ocr_profile = self._get_active_profile(ocr_service)
        ocr_extra = (ocr_profile or {}).get("extra_headers") or {}
        formula_ocr_profile = self._get_active_profile(formula_ocr_service)
        formula_ocr_extra = (formula_ocr_profile or {}).get("extra_headers") or {}
        image_understanding_profile = self._get_active_profile(image_understanding_service)
        image_understanding_extra = (image_understanding_profile or {}).get("extra_headers") or {}
        tts_profile = self._get_active_profile(tts_service)
        tts_extra = (tts_profile or {}).get("extra_headers") or {}
        asr_profile = self._get_active_profile(asr_service)
        asr_extra = (asr_profile or {}).get("extra_headers") or {}
        speech_eval_profile = self._get_active_profile(speech_eval_service)
        speech_eval_extra = (speech_eval_profile or {}).get("extra_headers") or {}

        current = self.load()
        provider_credentials = catalog.get("provider_credentials") or {}
        iflytek_credentials = provider_credentials.get("iflytek") or {}
        siliconflow_credentials = provider_credentials.get("siliconflow") or {}

        def credential(provider_values: dict[str, Any], key: str, *env_names: str) -> str:
            value = _as_str(provider_values.get(key))
            if value:
                return value
            for env_name in env_names:
                env_value = _as_str(
                    current.get(env_name)
                    or (os.getenv(env_name, "") if self._include_process_env() else "")
                )
                if env_value:
                    return env_value
            return ""

        iflytek_app_id = credential(
            iflytek_credentials,
            "app_id",
            "IFLYTEK_APPID",
            "IFLYTEK_OCR_APPID",
            "IFLYTEK_TTS_APPID",
            "IFLYTEK_EMBEDDING_APPID",
            "IFLYTEK_ASR_APPID",
            "IFLYTEK_SPEECH_EVAL_APPID",
        )
        iflytek_api_key = credential(
            iflytek_credentials,
            "api_key",
            "IFLYTEK_API_KEY",
            "IFLYTEK_OCR_API_KEY",
            "IFLYTEK_TTS_API_KEY",
            "IFLYTEK_EMBEDDING_API_KEY",
            "IFLYTEK_ASR_API_KEY",
            "IFLYTEK_SPEECH_EVAL_API_KEY",
        )
        iflytek_api_secret = credential(
            iflytek_credentials,
            "api_secret",
            "IFLYTEK_API_SECRET",
            "IFLYTEK_OCR_API_SECRET",
            "IFLYTEK_TTS_API_SECRET",
            "IFLYTEK_EMBEDDING_API_SECRET",
            "IFLYTEK_ASR_API_SECRET",
            "IFLYTEK_SPEECH_EVAL_API_SECRET",
        )
        iflytek_api_password = _as_str(iflytek_credentials.get("api_password"))
        if not iflytek_api_password and iflytek_api_key and iflytek_api_secret:
            iflytek_api_password = f"{iflytek_api_key}:{iflytek_api_secret}"
        if not iflytek_api_password:
            iflytek_api_password = credential(
                iflytek_credentials,
                "api_password",
                "IFLYTEK_API_PASSWORD",
                "IFLYTEK_SPARK_API_PASSWORD",
                "IFLYTEK_SEARCH_API_PASSWORD",
            )
        siliconflow_api_key = credential(
            siliconflow_credentials,
            "api_key",
            "SILICONFLOW_API_KEY",
            "SILICONFLOW_OCR_API_KEY",
        )

        def is_iflytek_llm() -> bool:
            return canonical_provider_name(_as_str((llm_profile or {}).get("binding"))) == "iflytek_spark_ws"

        def is_iflytek_embedding() -> bool:
            return _canonical_embedding_provider_name(_as_str((embedding_profile or {}).get("binding"))) == "iflytek_spark"

        def is_siliconflow_endpoint(profile: dict[str, Any] | None) -> bool:
            if not profile:
                return False
            binding = canonical_provider_name(_as_str(profile.get("binding")))
            provider = _as_str(profile.get("provider")).lower().replace("-", "_")
            base_url = _as_str(profile.get("base_url")).lower()
            return binding == "siliconflow" or provider == "siliconflow" or "siliconflow" in base_url

        def is_iflytek_search() -> bool:
            return _as_str((search_profile or {}).get("provider")).lower().replace("-", "_") == "iflytek_spark"

        ocr_provider = str(
            (ocr_profile or {}).get("provider")
            or current.get("SPARKWEAVE_OCR_PROVIDER", "iflytek")
        )
        ocr_is_siliconflow = ocr_provider.strip().lower().replace("-", "_") in {
            "siliconflow",
            "silicon_flow",
            "deepseekocr",
            "deepseek_ocr",
        }
        return {
            "BACKEND_PORT": current.get("BACKEND_PORT", os.getenv("BACKEND_PORT", "8001")),
            "FRONTEND_PORT": current.get("FRONTEND_PORT", os.getenv("FRONTEND_PORT", "3782")),
            "IFLYTEK_APPID": iflytek_app_id,
            "IFLYTEK_API_KEY": iflytek_api_key,
            "IFLYTEK_API_SECRET": iflytek_api_secret,
            "IFLYTEK_API_PASSWORD": iflytek_api_password,
            "SILICONFLOW_API_KEY": siliconflow_api_key,
            "LLM_BINDING": str((llm_profile or {}).get("binding") or "openai"),
            "LLM_MODEL": str((llm_model or {}).get("model") or ""),
            "LLM_API_KEY": str(
                ""
                if is_iflytek_llm() or is_siliconflow_endpoint(llm_profile)
                else (llm_profile or {}).get("api_key")
                or ""
            ),
            "LLM_HOST": str((llm_profile or {}).get("base_url") or ""),
            "LLM_API_VERSION": str((llm_profile or {}).get("api_version") or ""),
            "EMBEDDING_BINDING": str((embedding_profile or {}).get("binding") or "openai"),
            "EMBEDDING_MODEL": str((embedding_model or {}).get("model") or ""),
            "EMBEDDING_API_KEY": str(
                ""
                if is_iflytek_embedding() or is_siliconflow_endpoint(embedding_profile)
                else (embedding_profile or {}).get("api_key")
                or ""
            ),
            "EMBEDDING_HOST": str((embedding_profile or {}).get("base_url") or ""),
            "EMBEDDING_DIMENSION": str((embedding_model or {}).get("dimension") or 3072),
            "EMBEDDING_API_VERSION": str((embedding_profile or {}).get("api_version") or ""),
            "SEARCH_PROVIDER": str((search_profile or {}).get("provider") or ""),
            "SEARCH_API_KEY": str("" if is_iflytek_search() else (search_profile or {}).get("api_key") or ""),
            "SEARCH_BASE_URL": str((search_profile or {}).get("base_url") or ""),
            "SEARCH_PROXY": str((search_profile or {}).get("proxy") or ""),
            "SPARKWEAVE_OCR_PROVIDER": ocr_provider,
            "SPARKWEAVE_PDF_OCR_STRATEGY": str(
                (ocr_profile or {}).get("strategy")
                or current.get("SPARKWEAVE_PDF_OCR_STRATEGY", "auto")
            ),
            "SPARKWEAVE_OCR_TIMEOUT": str(
                (ocr_profile or {}).get("timeout") or ""
            ),
            "SPARKWEAVE_OCR_MAX_PAGES": str(
                (ocr_profile or {}).get("max_pages") or ""
            ),
            "SPARKWEAVE_OCR_DPI": str(
                (ocr_profile or {}).get("dpi") or ""
            ),
            "SPARKWEAVE_OCR_MIN_TEXT_CHARS": str(
                (ocr_profile or {}).get("min_text_chars") or ""
            ),
            "IFLYTEK_OCR_APPID": str(
                ocr_extra.get("app_id") or ("" if iflytek_app_id else current.get("IFLYTEK_OCR_APPID", ""))
            ),
            "IFLYTEK_OCR_API_KEY": str(
                ""
                if ocr_is_siliconflow
                else (ocr_profile or {}).get("api_key")
                or ("" if iflytek_api_key else current.get("IFLYTEK_OCR_API_KEY", ""))
            ),
            "IFLYTEK_OCR_API_SECRET": str(
                ocr_extra.get("api_secret")
                or ("" if iflytek_api_secret else current.get("IFLYTEK_OCR_API_SECRET", ""))
            ),
            "IFLYTEK_OCR_URL": str(
                current.get("IFLYTEK_OCR_URL", DEFAULT_IFLYTEK_OCR_URL)
                if ocr_is_siliconflow
                else ((ocr_profile or {}).get("base_url") or current.get("IFLYTEK_OCR_URL", DEFAULT_IFLYTEK_OCR_URL))
            ),
            "IFLYTEK_OCR_SERVICE_ID": str(
                ocr_extra.get("service_id")
                or current.get("IFLYTEK_OCR_SERVICE_ID", DEFAULT_IFLYTEK_OCR_SERVICE_ID)
            ),
            "IFLYTEK_OCR_CATEGORY": str(
                ocr_extra.get("category")
                or current.get("IFLYTEK_OCR_CATEGORY", DEFAULT_IFLYTEK_OCR_CATEGORY)
            ),
            "SILICONFLOW_OCR_API_KEY": str(
                ""
                if ocr_is_siliconflow and siliconflow_api_key
                else ((ocr_profile or {}).get("api_key") if ocr_is_siliconflow else "")
                or current.get("SILICONFLOW_OCR_API_KEY", "")
            ),
            "SILICONFLOW_OCR_BASE_URL": str(
                ((ocr_profile or {}).get("base_url") if ocr_is_siliconflow else "")
                or current.get("SILICONFLOW_OCR_BASE_URL", DEFAULT_SILICONFLOW_OCR_BASE_URL)
            ),
            "SILICONFLOW_OCR_MODEL": str(
                ocr_extra.get("model")
                or current.get("SILICONFLOW_OCR_MODEL", DEFAULT_SILICONFLOW_OCR_MODEL)
            ),
            "SILICONFLOW_OCR_PROMPT": str(
                ocr_extra.get("prompt")
                or current.get("SILICONFLOW_OCR_PROMPT", DEFAULT_SILICONFLOW_OCR_PROMPT)
            ),
            "SPARKWEAVE_TTS_PROVIDER": str(
                (tts_profile or {}).get("provider")
                or current.get("SPARKWEAVE_TTS_PROVIDER", "iflytek")
            ),
            "SPARKWEAVE_TTS_TIMEOUT": str(
                (tts_profile or {}).get("timeout") or current.get("SPARKWEAVE_TTS_TIMEOUT", "30")
            ),
            "IFLYTEK_TTS_APPID": str(
                tts_extra.get("app_id") or ("" if iflytek_app_id else current.get("IFLYTEK_TTS_APPID", ""))
            ),
            "IFLYTEK_TTS_API_KEY": str(
                (tts_profile or {}).get("api_key")
                or ("" if iflytek_api_key else current.get("IFLYTEK_TTS_API_KEY", ""))
            ),
            "IFLYTEK_TTS_API_SECRET": str(
                tts_extra.get("api_secret")
                or ("" if iflytek_api_secret else current.get("IFLYTEK_TTS_API_SECRET", ""))
            ),
            "IFLYTEK_TTS_URL": str(
                (tts_profile or {}).get("base_url")
                or current.get("IFLYTEK_TTS_URL", DEFAULT_IFLYTEK_TTS_URL)
            ),
            "IFLYTEK_TTS_VOICE": str(
                tts_extra.get("voice") or current.get("IFLYTEK_TTS_VOICE", DEFAULT_IFLYTEK_TTS_VOICE)
            ),
            "IFLYTEK_TTS_ENCODING": str(
                tts_extra.get("encoding") or current.get("IFLYTEK_TTS_ENCODING", "lame")
            ),
            "IFLYTEK_TTS_SAMPLE_RATE": str(
                tts_extra.get("sample_rate") or current.get("IFLYTEK_TTS_SAMPLE_RATE", "24000")
            ),
            "IFLYTEK_TTS_CHANNELS": str(
                tts_extra.get("channels") or current.get("IFLYTEK_TTS_CHANNELS", "1")
            ),
            "IFLYTEK_TTS_BIT_DEPTH": str(
                tts_extra.get("bit_depth") or current.get("IFLYTEK_TTS_BIT_DEPTH", "16")
            ),
            "IFLYTEK_TTS_FRAME_SIZE": str(
                tts_extra.get("frame_size") or current.get("IFLYTEK_TTS_FRAME_SIZE", "0")
            ),
            "IFLYTEK_TTS_SPEED": str(
                tts_extra.get("speed") or current.get("IFLYTEK_TTS_SPEED", "50")
            ),
            "IFLYTEK_TTS_VOLUME": str(
                tts_extra.get("volume") or current.get("IFLYTEK_TTS_VOLUME", "50")
            ),
            "IFLYTEK_TTS_PITCH": str(
                tts_extra.get("pitch") or current.get("IFLYTEK_TTS_PITCH", "50")
            ),
            "SPARKWEAVE_ASR_PROVIDER": str(
                (asr_profile or {}).get("provider")
                or current.get("SPARKWEAVE_ASR_PROVIDER", "iflytek")
            ),
            "SPARKWEAVE_ASR_TIMEOUT": str(
                (asr_profile or {}).get("timeout") or current.get("SPARKWEAVE_ASR_TIMEOUT", "60")
            ),
            "IFLYTEK_ASR_APPID": str(
                asr_extra.get("app_id") or ("" if iflytek_app_id else current.get("IFLYTEK_ASR_APPID", ""))
            ),
            "IFLYTEK_ASR_API_KEY": str(
                (asr_profile or {}).get("api_key")
                or ("" if iflytek_api_key else current.get("IFLYTEK_ASR_API_KEY", ""))
            ),
            "IFLYTEK_ASR_API_SECRET": str(
                asr_extra.get("api_secret")
                or ("" if iflytek_api_secret else current.get("IFLYTEK_ASR_API_SECRET", ""))
            ),
            "IFLYTEK_ASR_URL": str(
                (asr_profile or {}).get("base_url")
                or current.get("IFLYTEK_ASR_URL", DEFAULT_IFLYTEK_ASR_URL)
            ),
            "IFLYTEK_ASR_LANGUAGE": str(
                asr_extra.get("language") or current.get("IFLYTEK_ASR_LANGUAGE", "zh_cn")
            ),
            "IFLYTEK_ASR_ACCENT": str(
                asr_extra.get("accent") or current.get("IFLYTEK_ASR_ACCENT", "mandarin")
            ),
            "IFLYTEK_ASR_DOMAIN": str(
                asr_extra.get("domain") or current.get("IFLYTEK_ASR_DOMAIN", "iat")
            ),
            "IFLYTEK_ASR_VAD_EOS": str(
                asr_extra.get("vad_eos") or current.get("IFLYTEK_ASR_VAD_EOS", "3000")
            ),
            "SPARKWEAVE_SPEECH_EVAL_PROVIDER": str(
                (speech_eval_profile or {}).get("provider")
                or current.get("SPARKWEAVE_SPEECH_EVAL_PROVIDER", "iflytek")
            ),
            "SPARKWEAVE_SPEECH_EVAL_TIMEOUT": str(
                (speech_eval_profile or {}).get("timeout")
                or current.get("SPARKWEAVE_SPEECH_EVAL_TIMEOUT", "60")
            ),
            "IFLYTEK_SPEECH_EVAL_APPID": str(
                speech_eval_extra.get("app_id")
                or ("" if iflytek_app_id else current.get("IFLYTEK_SPEECH_EVAL_APPID", ""))
            ),
            "IFLYTEK_SPEECH_EVAL_API_KEY": str(
                (speech_eval_profile or {}).get("api_key")
                or ("" if iflytek_api_key else current.get("IFLYTEK_SPEECH_EVAL_API_KEY", ""))
            ),
            "IFLYTEK_SPEECH_EVAL_API_SECRET": str(
                speech_eval_extra.get("api_secret")
                or ("" if iflytek_api_secret else current.get("IFLYTEK_SPEECH_EVAL_API_SECRET", ""))
            ),
            "IFLYTEK_SPEECH_EVAL_URL": str(
                (speech_eval_profile or {}).get("base_url")
                or current.get("IFLYTEK_SPEECH_EVAL_URL", DEFAULT_IFLYTEK_SPEECH_EVAL_URL)
            ),
            "IFLYTEK_SPEECH_EVAL_CATEGORY": str(
                speech_eval_extra.get("category")
                or current.get("IFLYTEK_SPEECH_EVAL_CATEGORY", "read_sentence")
            ),
            "IFLYTEK_SPEECH_EVAL_LANGUAGE": str(
                speech_eval_extra.get("language") or current.get("IFLYTEK_SPEECH_EVAL_LANGUAGE", "zh_cn")
            ),
            "SPARKWEAVE_FORMULA_OCR_PROVIDER": str(
                (formula_ocr_profile or {}).get("provider")
                or current.get("SPARKWEAVE_FORMULA_OCR_PROVIDER", "iflytek")
            ),
            "IFLYTEK_FORMULA_URL": str(
                (formula_ocr_profile or {}).get("base_url")
                or current.get("IFLYTEK_FORMULA_URL", DEFAULT_IFLYTEK_FORMULA_URL)
            ),
            "IFLYTEK_FORMULA_APPID": str(
                formula_ocr_extra.get("app_id")
                or ("" if iflytek_app_id else current.get("IFLYTEK_FORMULA_APPID", ""))
            ),
            "IFLYTEK_FORMULA_API_KEY": str(
                (formula_ocr_profile or {}).get("api_key")
                or ("" if iflytek_api_key else current.get("IFLYTEK_FORMULA_API_KEY", ""))
            ),
            "IFLYTEK_FORMULA_API_SECRET": str(
                formula_ocr_extra.get("api_secret")
                or ("" if iflytek_api_secret else current.get("IFLYTEK_FORMULA_API_SECRET", ""))
            ),
            "IFLYTEK_FORMULA_ENT": str(
                formula_ocr_extra.get("ent") or current.get("IFLYTEK_FORMULA_ENT", DEFAULT_IFLYTEK_FORMULA_ENT)
            ),
            "IFLYTEK_FORMULA_AUE": str(
                formula_ocr_extra.get("aue") or current.get("IFLYTEK_FORMULA_AUE", DEFAULT_IFLYTEK_FORMULA_AUE)
            ),
            "IFLYTEK_FORMULA_TIMEOUT": str(
                (formula_ocr_profile or {}).get("timeout") or current.get("IFLYTEK_FORMULA_TIMEOUT", "30")
            ),
            "SPARKWEAVE_IMAGE_UNDERSTANDING_PROVIDER": str(
                (image_understanding_profile or {}).get("provider")
                or current.get("SPARKWEAVE_IMAGE_UNDERSTANDING_PROVIDER", "iflytek")
            ),
            "IFLYTEK_VISION_PROTOCOL": str(
                image_understanding_extra.get("protocol")
                or current.get("IFLYTEK_VISION_PROTOCOL", DEFAULT_IFLYTEK_VISION_PROTOCOL)
            ),
            "IFLYTEK_VISION_URL": str(
                (image_understanding_profile or {}).get("base_url")
                or current.get("IFLYTEK_VISION_URL", DEFAULT_IFLYTEK_VISION_URL)
            ),
            "IFLYTEK_VISION_APPID": str(
                image_understanding_extra.get("app_id")
                or ("" if iflytek_app_id else current.get("IFLYTEK_VISION_APPID", ""))
            ),
            "IFLYTEK_VISION_API_KEY": str(
                (image_understanding_profile or {}).get("api_key")
                or ("" if iflytek_api_key else current.get("IFLYTEK_VISION_API_KEY", ""))
            ),
            "IFLYTEK_VISION_API_SECRET": str(
                image_understanding_extra.get("api_secret")
                or ("" if iflytek_api_secret else current.get("IFLYTEK_VISION_API_SECRET", ""))
            ),
            "IFLYTEK_VISION_DOMAIN": str(
                image_understanding_extra.get("domain") or current.get("IFLYTEK_VISION_DOMAIN", DEFAULT_IFLYTEK_VISION_DOMAIN)
            ),
            "IFLYTEK_VISION_MAX_TOKENS": str(
                image_understanding_extra.get("max_tokens") or current.get("IFLYTEK_VISION_MAX_TOKENS", "2048")
            ),
            "IFLYTEK_VISION_TEMPERATURE": str(
                image_understanding_extra.get("temperature") or current.get("IFLYTEK_VISION_TEMPERATURE", "0.2")
            ),
            "IFLYTEK_VISION_TOP_K": str(
                image_understanding_extra.get("top_k") or current.get("IFLYTEK_VISION_TOP_K", "4")
            ),
            "IFLYTEK_VISION_TIMEOUT": str(
                (image_understanding_profile or {}).get("timeout") or current.get("IFLYTEK_VISION_TIMEOUT", "45")
            ),
            "IFLYTEK_VISION_UID": str(
                image_understanding_extra.get("uid") or current.get("IFLYTEK_VISION_UID", "sparkweave")
            ),
        }

    def _get_active_profile(self, service: dict[str, Any]) -> dict[str, Any] | None:
        active_id = service.get("active_profile_id")
        profiles = service.get("profiles", [])
        for profile in profiles:
            if profile.get("id") == active_id:
                return profile
        return profiles[0] if profiles else None

    def _get_active_model(
        self,
        service: dict[str, Any],
        profile: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not profile:
            return None
        active_id = service.get("active_model_id")
        models = profile.get("models", [])
        for model in models:
            if model.get("id") == active_id:
                return model
        return models[0] if models else None


_env_store: EnvStore | None = None


def get_env_store() -> EnvStore:
    """Return the active NG env store."""
    global _env_store
    if _env_store is None:
        _env_store = EnvStore()
    return _env_store


def _service_shell() -> dict[str, Any]:
    return {"active_profile_id": None, "active_model_id": None, "profiles": []}


def _search_shell() -> dict[str, Any]:
    return {"active_profile_id": None, "profiles": []}


def _ocr_shell() -> dict[str, Any]:
    return {"active_profile_id": None, "profiles": []}


def _formula_ocr_shell() -> dict[str, Any]:
    return {"active_profile_id": None, "profiles": []}


def _image_understanding_shell() -> dict[str, Any]:
    return {"active_profile_id": None, "profiles": []}


def _tts_shell() -> dict[str, Any]:
    return {"active_profile_id": None, "profiles": []}


def _asr_shell() -> dict[str, Any]:
    return {"active_profile_id": None, "profiles": []}


def _speech_eval_shell() -> dict[str, Any]:
    return {"active_profile_id": None, "profiles": []}


def _provider_credentials_shell() -> dict[str, Any]:
    return {
        "iflytek": {
            "app_id": "",
            "api_key": "",
            "api_secret": "",
            "api_password": "",
        },
        "siliconflow": {
            "api_key": "",
        },
    }


def _default_catalog() -> dict[str, Any]:
    return {
        "version": 1,
        "provider_credentials": _provider_credentials_shell(),
        "services": {
            "llm": _service_shell(),
            "embedding": _service_shell(),
            "search": _search_shell(),
            "ocr": _ocr_shell(),
            "formula_ocr": _formula_ocr_shell(),
            "image_understanding": _image_understanding_shell(),
            "tts": _tts_shell(),
            "asr": _asr_shell(),
            "speech_eval": _speech_eval_shell(),
        },
    }


class ModelCatalogService:
    """Read the runtime model catalog from ``data/user/settings``."""

    _instance: "ModelCatalogService | None" = None

    def __init__(self, path: Path | None = None):
        self.path = path or get_path_service().get_settings_file("model_catalog")

    @classmethod
    def get_instance(cls, path: Path | None = None) -> "ModelCatalogService":
        if cls._instance is None:
            cls._instance = cls(path)
        return cls._instance

    def load(self) -> dict[str, Any]:
        catalog = _default_catalog()
        loaded_from_disk = self.path.exists()
        if loaded_from_disk:
            loaded = json.loads(self.path.read_text(encoding="utf-8") or "{}")
            catalog.update({k: v for k, v in loaded.items() if k != "services"})
            catalog["services"].update(loaded.get("services", {}))
        hydrated = self._hydrate_missing_services_from_env(catalog)
        synced = self._sync_active_services_from_env(
            catalog,
            only_default_profiles=loaded_from_disk,
        )
        credential_synced = self._sync_provider_credentials(catalog)
        self._normalize(catalog)
        if hydrated or synced or credential_synced or not self.path.exists():
            self.save(catalog)
        return catalog

    def save(self, catalog: dict[str, Any]) -> dict[str, Any]:
        """Normalize and persist the model catalog."""
        normalized = deepcopy(catalog)
        self._sync_provider_credentials(normalized)
        self._normalize(normalized)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
        return normalized

    def apply(self, catalog: dict[str, Any] | None = None) -> dict[str, str]:
        """Persist the catalog and write active selections to `.env`."""
        current = self.save(catalog or self.load())
        rendered = get_env_store().render_from_catalog(current)
        get_env_store().write(rendered)
        return rendered

    def _hydrate_missing_services_from_env(self, catalog: dict[str, Any]) -> bool:
        summary = get_env_store().as_summary()
        services = catalog.setdefault("services", {})
        changed = False

        llm_service = services.setdefault("llm", _service_shell())
        if not llm_service.get("profiles") and (summary.llm["model"] or summary.llm["host"]):
            profile_id = "llm-profile-default"
            model_id = "llm-model-default"
            services["llm"] = {
                "active_profile_id": profile_id,
                "active_model_id": model_id,
                "profiles": [
                    {
                        "id": profile_id,
                        "name": "Default LLM Endpoint",
                        "binding": summary.llm["binding"] or "openai",
                        "base_url": summary.llm["host"],
                        "api_key": summary.llm["api_key"],
                        "api_version": summary.llm["api_version"],
                        "extra_headers": {},
                        "models": [
                            {
                                "id": model_id,
                                "name": summary.llm["model"] or "Default Model",
                                "model": summary.llm["model"],
                            }
                        ],
                    }
                ],
            }
            changed = True

        embedding_service = services.setdefault("embedding", _service_shell())
        if not embedding_service.get("profiles") and (
            summary.embedding["model"] or summary.embedding["host"]
        ):
            profile_id = "embedding-profile-default"
            model_id = "embedding-model-default"
            services["embedding"] = {
                "active_profile_id": profile_id,
                "active_model_id": model_id,
                "profiles": [
                    {
                        "id": profile_id,
                        "name": "Default Embedding Endpoint",
                        "binding": summary.embedding["binding"] or "openai",
                        "base_url": summary.embedding["host"],
                        "api_key": summary.embedding["api_key"],
                        "api_version": summary.embedding["api_version"],
                        "extra_headers": {},
                        "models": [
                            {
                                "id": model_id,
                                "name": summary.embedding["model"] or "Default Embedding Model",
                                "model": summary.embedding["model"],
                                "dimension": summary.embedding["dimension"] or "3072",
                            }
                        ],
                    }
                ],
            }
            changed = True

        search_service = services.setdefault("search", _search_shell())
        if not search_service.get("profiles") and (
            summary.search["provider"] or summary.search["base_url"] or summary.search["api_key"]
        ):
            profile_id = "search-profile-default"
            services["search"] = {
                "active_profile_id": profile_id,
                "profiles": [
                    {
                        "id": profile_id,
                        "name": "Default Search Provider",
                        "provider": summary.search["provider"] or "brave",
                        "base_url": summary.search["base_url"],
                        "api_key": summary.search["api_key"],
                        "api_version": "",
                        "proxy": summary.search["proxy"],
                        "models": [],
                    }
                ],
            }
            changed = True

        ocr_service = services.setdefault("ocr", _ocr_shell())
        ocr_provider = summary.ocr["provider"].strip().lower().replace("-", "_")
        ocr_is_siliconflow = ocr_provider in {
            "siliconflow",
            "silicon_flow",
            "deepseekocr",
            "deepseek_ocr",
        }
        if not ocr_service.get("profiles") and (
            summary.ocr["provider"]
            or summary.ocr["app_id"]
            or summary.ocr["api_key"]
            or summary.ocr["api_secret"]
            or summary.ocr["siliconflow_api_key"]
        ):
            profile_id = "ocr-profile-default"
            services["ocr"] = {
                "active_profile_id": profile_id,
                "profiles": [
                    {
                        "id": profile_id,
                        "name": "Default OCR Provider",
                        "provider": summary.ocr["provider"] or "iflytek",
                        "strategy": summary.ocr["strategy"] or "auto",
                        "base_url": (
                            summary.ocr["siliconflow_base_url"]
                            if ocr_is_siliconflow
                            else summary.ocr["url"]
                        ),
                        "api_key": (
                            summary.ocr["siliconflow_api_key"]
                            if ocr_is_siliconflow
                            else summary.ocr["api_key"]
                        ),
                        "extra_headers": {
                            "app_id": summary.ocr["app_id"],
                            "api_secret": summary.ocr["api_secret"],
                            "service_id": summary.ocr["service_id"] or DEFAULT_IFLYTEK_OCR_SERVICE_ID,
                            "category": summary.ocr["category"] or DEFAULT_IFLYTEK_OCR_CATEGORY,
                            "model": summary.ocr["siliconflow_model"] or DEFAULT_SILICONFLOW_OCR_MODEL,
                            "prompt": summary.ocr["siliconflow_prompt"] or DEFAULT_SILICONFLOW_OCR_PROMPT,
                        },
                        "models": [],
                    }
                ],
            }
            changed = True

        tts_service = services.setdefault("tts", _tts_shell())
        if not tts_service.get("profiles") and (
            summary.tts["provider"]
            or summary.tts["app_id"]
            or summary.tts["api_key"]
            or summary.tts["api_secret"]
        ):
            profile_id = "tts-profile-default"
            services["tts"] = {
                "active_profile_id": profile_id,
                "profiles": [
                    {
                        "id": profile_id,
                        "name": "Default TTS Provider",
                        "provider": summary.tts["provider"] or "iflytek",
                        "base_url": summary.tts["url"],
                        "api_key": summary.tts["api_key"],
                        "timeout": summary.tts["timeout"] or "30",
                        "extra_headers": {
                            "app_id": summary.tts["app_id"],
                            "api_secret": summary.tts["api_secret"],
                            "voice": summary.tts["voice"] or DEFAULT_IFLYTEK_TTS_VOICE,
                            "encoding": summary.tts["encoding"] or "lame",
                            "sample_rate": summary.tts["sample_rate"] or "24000",
                            "channels": summary.tts["channels"] or "1",
                            "bit_depth": summary.tts["bit_depth"] or "16",
                            "frame_size": summary.tts["frame_size"] or "0",
                            "speed": summary.tts["speed"] or "50",
                            "volume": summary.tts["volume"] or "50",
                            "pitch": summary.tts["pitch"] or "50",
                        },
                        "models": [],
                    }
                ],
            }
            changed = True

        asr_service = services.setdefault("asr", _asr_shell())
        if not asr_service.get("profiles") and (
            summary.asr["provider"]
            or summary.asr["app_id"]
            or summary.asr["api_key"]
            or summary.asr["api_secret"]
        ):
            profile_id = "asr-profile-default"
            services["asr"] = {
                "active_profile_id": profile_id,
                "profiles": [
                    {
                        "id": profile_id,
                        "name": "Default ASR Provider",
                        "provider": summary.asr["provider"] or "iflytek",
                        "base_url": summary.asr["url"],
                        "api_key": summary.asr["api_key"],
                        "timeout": summary.asr["timeout"] or "60",
                        "extra_headers": {
                            "app_id": summary.asr["app_id"],
                            "api_secret": summary.asr["api_secret"],
                            "language": summary.asr["language"] or "zh_cn",
                            "accent": summary.asr["accent"] or "mandarin",
                            "domain": summary.asr["domain"] or "iat",
                            "vad_eos": summary.asr["vad_eos"] or "3000",
                        },
                        "models": [],
                    }
                ],
            }
            changed = True

        speech_eval_service = services.setdefault("speech_eval", _speech_eval_shell())
        if not speech_eval_service.get("profiles") and (
            summary.speech_eval["provider"]
            or summary.speech_eval["app_id"]
            or summary.speech_eval["api_key"]
            or summary.speech_eval["api_secret"]
        ):
            profile_id = "speech-eval-profile-default"
            services["speech_eval"] = {
                "active_profile_id": profile_id,
                "profiles": [
                    {
                        "id": profile_id,
                        "name": "Default Speech Evaluation Provider",
                        "provider": summary.speech_eval["provider"] or "iflytek",
                        "base_url": summary.speech_eval["url"],
                        "api_key": summary.speech_eval["api_key"],
                        "timeout": summary.speech_eval["timeout"] or "60",
                        "extra_headers": {
                            "app_id": summary.speech_eval["app_id"],
                            "api_secret": summary.speech_eval["api_secret"],
                            "category": summary.speech_eval["category"] or "read_sentence",
                            "language": summary.speech_eval["language"] or "zh_cn",
                        },
                        "models": [],
                    }
                ],
            }
            changed = True

        return changed

    def _sync_active_services_from_env(
        self,
        catalog: dict[str, Any],
        *,
        only_default_profiles: bool = False,
    ) -> bool:
        """Sync active catalog values from explicitly present `.env` keys."""
        env_values = get_env_store().load()
        if not env_values:
            return False

        summary = get_env_store().as_summary()
        services = catalog.setdefault("services", {})
        changed = False

        def can_sync_service(service_name: str, default_profile_id: str) -> bool:
            if not only_default_profiles:
                return True
            service = services.get(service_name) or {}
            profiles = service.get("profiles") or []
            active_id = service.get("active_profile_id")
            if not profiles:
                return True
            return active_id in (None, "", default_profile_id)

        def ensure_llm_profile() -> tuple[dict[str, Any], dict[str, Any]]:
            service = services.setdefault("llm", _service_shell())
            profiles = service.setdefault("profiles", [])
            if not profiles:
                profile_id = "llm-profile-default"
                model_id = "llm-model-default"
                profile = {
                    "id": profile_id,
                    "name": "Default LLM Endpoint",
                    "binding": "openai",
                    "base_url": "",
                    "api_key": "",
                    "api_version": "",
                    "extra_headers": {},
                    "models": [{"id": model_id, "name": "Default Model", "model": ""}],
                }
                service["profiles"] = [profile]
                service["active_profile_id"] = profile_id
                service["active_model_id"] = model_id
            profile = self.get_active_profile(catalog, "llm") or service["profiles"][0]
            model = self.get_active_model(catalog, "llm") or profile.setdefault("models", [{}])[0]
            return profile, model

        def ensure_embedding_profile() -> tuple[dict[str, Any], dict[str, Any]]:
            service = services.setdefault("embedding", _service_shell())
            profiles = service.setdefault("profiles", [])
            if not profiles:
                profile_id = "embedding-profile-default"
                model_id = "embedding-model-default"
                profile = {
                    "id": profile_id,
                    "name": "Default Embedding Endpoint",
                    "binding": "openai",
                    "base_url": "",
                    "api_key": "",
                    "api_version": "",
                    "extra_headers": {},
                    "models": [
                        {
                            "id": model_id,
                            "name": "Default Embedding Model",
                            "model": "",
                            "dimension": "3072",
                        }
                    ],
                }
                service["profiles"] = [profile]
                service["active_profile_id"] = profile_id
                service["active_model_id"] = model_id
            profile = self.get_active_profile(catalog, "embedding") or service["profiles"][0]
            model = self.get_active_model(catalog, "embedding") or profile.setdefault("models", [{}])[0]
            return profile, model

        def ensure_search_profile() -> dict[str, Any]:
            service = services.setdefault("search", _search_shell())
            profiles = service.setdefault("profiles", [])
            if not profiles:
                profile_id = "search-profile-default"
                profile = {
                    "id": profile_id,
                    "name": "Default Search Provider",
                    "provider": "brave",
                    "base_url": "",
                    "api_key": "",
                    "api_version": "",
                    "proxy": "",
                    "models": [],
                }
                service["profiles"] = [profile]
                service["active_profile_id"] = profile_id
            return self.get_active_profile(catalog, "search") or service["profiles"][0]

        def ensure_ocr_profile() -> dict[str, Any]:
            service = services.setdefault("ocr", _ocr_shell())
            profiles = service.setdefault("profiles", [])
            if not profiles:
                profile_id = "ocr-profile-default"
                profile = {
                    "id": profile_id,
                    "name": "Default OCR Provider",
                    "provider": "iflytek",
                    "strategy": "auto",
                    "base_url": DEFAULT_IFLYTEK_OCR_URL,
                    "api_key": "",
                    "timeout": DEFAULT_OCR_TIMEOUT,
                    "max_pages": DEFAULT_OCR_MAX_PAGES,
                    "dpi": DEFAULT_OCR_DPI,
                    "min_text_chars": DEFAULT_OCR_MIN_TEXT_CHARS,
                    "extra_headers": {
                        "app_id": "",
                        "api_secret": "",
                        "service_id": DEFAULT_IFLYTEK_OCR_SERVICE_ID,
                        "category": DEFAULT_IFLYTEK_OCR_CATEGORY,
                    },
                    "models": [],
                }
                service["profiles"] = [profile]
                service["active_profile_id"] = profile_id
            return self.get_active_profile(catalog, "ocr") or service["profiles"][0]

        def ensure_tts_profile() -> dict[str, Any]:
            service = services.setdefault("tts", _tts_shell())
            profiles = service.setdefault("profiles", [])
            if not profiles:
                profile_id = "tts-profile-default"
                profile = {
                    "id": profile_id,
                    "name": "Default TTS Provider",
                    "provider": "iflytek",
                    "base_url": DEFAULT_IFLYTEK_TTS_URL,
                    "api_key": "",
                    "timeout": "30",
                    "extra_headers": {
                        "app_id": "",
                        "api_secret": "",
                        "voice": DEFAULT_IFLYTEK_TTS_VOICE,
                        "encoding": "lame",
                        "sample_rate": "24000",
                        "channels": "1",
                        "bit_depth": "16",
                        "frame_size": "0",
                        "speed": "50",
                        "volume": "50",
                        "pitch": "50",
                    },
                    "models": [],
                }
                service["profiles"] = [profile]
                service["active_profile_id"] = profile_id
            return self.get_active_profile(catalog, "tts") or service["profiles"][0]

        def ensure_asr_profile() -> dict[str, Any]:
            service = services.setdefault("asr", _asr_shell())
            profiles = service.setdefault("profiles", [])
            if not profiles:
                profile_id = "asr-profile-default"
                profile = {
                    "id": profile_id,
                    "name": "Default ASR Provider",
                    "provider": "iflytek",
                    "base_url": DEFAULT_IFLYTEK_ASR_URL,
                    "api_key": "",
                    "timeout": "60",
                    "extra_headers": {
                        "app_id": "",
                        "api_secret": "",
                        "language": "zh_cn",
                        "accent": "mandarin",
                        "domain": "iat",
                        "vad_eos": "3000",
                    },
                    "models": [],
                }
                service["profiles"] = [profile]
                service["active_profile_id"] = profile_id
            return self.get_active_profile(catalog, "asr") or service["profiles"][0]

        def ensure_speech_eval_profile() -> dict[str, Any]:
            service = services.setdefault("speech_eval", _speech_eval_shell())
            profiles = service.setdefault("profiles", [])
            if not profiles:
                profile_id = "speech-eval-profile-default"
                profile = {
                    "id": profile_id,
                    "name": "Default Speech Evaluation Provider",
                    "provider": "iflytek",
                    "base_url": DEFAULT_IFLYTEK_SPEECH_EVAL_URL,
                    "api_key": "",
                    "timeout": "60",
                    "extra_headers": {
                        "app_id": "",
                        "api_secret": "",
                        "category": "read_sentence",
                        "language": "zh_cn",
                    },
                    "models": [],
                }
                service["profiles"] = [profile]
                service["active_profile_id"] = profile_id
            return self.get_active_profile(catalog, "speech_eval") or service["profiles"][0]

        if {"LLM_BINDING", "LLM_MODEL", "LLM_API_KEY", "LLM_HOST", "LLM_API_VERSION"}.intersection(
            env_values
        ) and can_sync_service("llm", "llm-profile-default"):
            profile, model = ensure_llm_profile()
            for env_key, target, value in (
                ("LLM_BINDING", profile, summary.llm["binding"]),
                ("LLM_API_KEY", profile, summary.llm["api_key"]),
                ("LLM_HOST", profile, summary.llm["host"]),
                ("LLM_API_VERSION", profile, summary.llm["api_version"]),
            ):
                field_name = "base_url" if env_key == "LLM_HOST" else env_key.removeprefix("LLM_").lower()
                if env_key in env_values and target.get(field_name) != value:
                    target[field_name] = value
                    changed = True
            if "LLM_MODEL" in env_values:
                if model.get("model") != summary.llm["model"]:
                    model["model"] = summary.llm["model"]
                    changed = True
                if summary.llm["model"] and model.get("name") != summary.llm["model"]:
                    model["name"] = summary.llm["model"]
                    changed = True

        if {
            "EMBEDDING_BINDING",
            "EMBEDDING_MODEL",
            "EMBEDDING_API_KEY",
            "EMBEDDING_HOST",
            "EMBEDDING_DIMENSION",
            "EMBEDDING_API_VERSION",
        }.intersection(env_values) and can_sync_service("embedding", "embedding-profile-default"):
            profile, model = ensure_embedding_profile()
            for env_key, target, value in (
                ("EMBEDDING_BINDING", profile, summary.embedding["binding"]),
                ("EMBEDDING_API_KEY", profile, summary.embedding["api_key"]),
                ("EMBEDDING_HOST", profile, summary.embedding["host"]),
                ("EMBEDDING_API_VERSION", profile, summary.embedding["api_version"]),
            ):
                field_name = (
                    "base_url"
                    if env_key == "EMBEDDING_HOST"
                    else env_key.removeprefix("EMBEDDING_").lower()
                )
                if env_key in env_values and target.get(field_name) != value:
                    target[field_name] = value
                    changed = True
            if "EMBEDDING_MODEL" in env_values:
                if model.get("model") != summary.embedding["model"]:
                    model["model"] = summary.embedding["model"]
                    changed = True
                if summary.embedding["model"] and model.get("name") != summary.embedding["model"]:
                    model["name"] = summary.embedding["model"]
                    changed = True
            if (
                "EMBEDDING_DIMENSION" in env_values
                and model.get("dimension") != summary.embedding["dimension"]
            ):
                model["dimension"] = summary.embedding["dimension"]
                changed = True

        if {"SEARCH_PROVIDER", "SEARCH_API_KEY", "SEARCH_BASE_URL", "SEARCH_PROXY"}.intersection(
            env_values
        ) and can_sync_service("search", "search-profile-default"):
            profile = ensure_search_profile()
            for env_key, value in (
                ("SEARCH_PROVIDER", summary.search["provider"]),
                ("SEARCH_API_KEY", summary.search["api_key"]),
                ("SEARCH_BASE_URL", summary.search["base_url"]),
                ("SEARCH_PROXY", summary.search["proxy"]),
            ):
                field_name = "base_url" if env_key == "SEARCH_BASE_URL" else env_key.removeprefix("SEARCH_").lower()
                if env_key in env_values and profile.get(field_name) != value:
                    profile[field_name] = value
                    changed = True

        ocr_keys = {
            "SPARKWEAVE_OCR_PROVIDER",
            "SPARKWEAVE_PDF_OCR_STRATEGY",
            "SPARKWEAVE_OCR_TIMEOUT",
            "SPARKWEAVE_OCR_MAX_PAGES",
            "SPARKWEAVE_OCR_DPI",
            "SPARKWEAVE_OCR_MIN_TEXT_CHARS",
            "IFLYTEK_OCR_APPID",
            "IFLYTEK_OCR_API_KEY",
            "IFLYTEK_OCR_API_SECRET",
            "IFLYTEK_OCR_URL",
            "IFLYTEK_OCR_SERVICE_ID",
            "IFLYTEK_OCR_CATEGORY",
            "SILICONFLOW_OCR_API_KEY",
            "SILICONFLOW_OCR_BASE_URL",
            "SILICONFLOW_OCR_MODEL",
            "SILICONFLOW_OCR_PROMPT",
        }
        if ocr_keys.intersection(env_values) and can_sync_service("ocr", "ocr-profile-default"):
            profile = ensure_ocr_profile()
            extra_headers = profile.setdefault("extra_headers", {})
            for env_key, field_name, value in (
                ("SPARKWEAVE_OCR_PROVIDER", "provider", summary.ocr["provider"]),
                ("SPARKWEAVE_PDF_OCR_STRATEGY", "strategy", summary.ocr["strategy"]),
                ("SPARKWEAVE_OCR_TIMEOUT", "timeout", summary.ocr["timeout"]),
                ("SPARKWEAVE_OCR_MAX_PAGES", "max_pages", summary.ocr["max_pages"]),
                ("SPARKWEAVE_OCR_DPI", "dpi", summary.ocr["dpi"]),
                ("SPARKWEAVE_OCR_MIN_TEXT_CHARS", "min_text_chars", summary.ocr["min_text_chars"]),
                ("IFLYTEK_OCR_API_KEY", "api_key", summary.ocr["api_key"]),
                ("IFLYTEK_OCR_URL", "base_url", summary.ocr["url"]),
                ("SILICONFLOW_OCR_API_KEY", "api_key", summary.ocr["siliconflow_api_key"]),
                ("SILICONFLOW_OCR_BASE_URL", "base_url", summary.ocr["siliconflow_base_url"]),
            ):
                if env_key in env_values and profile.get(field_name) != value:
                    profile[field_name] = value
                    changed = True
            for env_key, field_name, value in (
                ("IFLYTEK_OCR_APPID", "app_id", summary.ocr["app_id"]),
                ("IFLYTEK_OCR_API_SECRET", "api_secret", summary.ocr["api_secret"]),
                ("IFLYTEK_OCR_SERVICE_ID", "service_id", summary.ocr["service_id"]),
                ("IFLYTEK_OCR_CATEGORY", "category", summary.ocr["category"]),
                ("SILICONFLOW_OCR_MODEL", "model", summary.ocr["siliconflow_model"]),
                ("SILICONFLOW_OCR_PROMPT", "prompt", summary.ocr["siliconflow_prompt"]),
            ):
                if env_key in env_values and extra_headers.get(field_name) != value:
                    extra_headers[field_name] = value
                    changed = True

        tts_keys = {
            "SPARKWEAVE_TTS_PROVIDER",
            "SPARKWEAVE_TTS_TIMEOUT",
            "IFLYTEK_TTS_APPID",
            "IFLYTEK_TTS_API_KEY",
            "IFLYTEK_TTS_API_SECRET",
            "IFLYTEK_TTS_URL",
            "IFLYTEK_TTS_VOICE",
            "IFLYTEK_TTS_ENCODING",
            "IFLYTEK_TTS_SAMPLE_RATE",
            "IFLYTEK_TTS_CHANNELS",
            "IFLYTEK_TTS_BIT_DEPTH",
            "IFLYTEK_TTS_FRAME_SIZE",
            "IFLYTEK_TTS_SPEED",
            "IFLYTEK_TTS_VOLUME",
            "IFLYTEK_TTS_PITCH",
        }
        if tts_keys.intersection(env_values) and can_sync_service("tts", "tts-profile-default"):
            profile = ensure_tts_profile()
            extra_headers = profile.setdefault("extra_headers", {})
            for env_key, field_name, value in (
                ("SPARKWEAVE_TTS_PROVIDER", "provider", summary.tts["provider"]),
                ("SPARKWEAVE_TTS_TIMEOUT", "timeout", summary.tts["timeout"]),
                ("IFLYTEK_TTS_API_KEY", "api_key", summary.tts["api_key"]),
                ("IFLYTEK_TTS_URL", "base_url", summary.tts["url"]),
            ):
                if env_key in env_values and profile.get(field_name) != value:
                    profile[field_name] = value
                    changed = True
            for env_key, field_name, value in (
                ("IFLYTEK_TTS_APPID", "app_id", summary.tts["app_id"]),
                ("IFLYTEK_TTS_API_SECRET", "api_secret", summary.tts["api_secret"]),
                ("IFLYTEK_TTS_VOICE", "voice", summary.tts["voice"]),
                ("IFLYTEK_TTS_ENCODING", "encoding", summary.tts["encoding"]),
                ("IFLYTEK_TTS_SAMPLE_RATE", "sample_rate", summary.tts["sample_rate"]),
                ("IFLYTEK_TTS_CHANNELS", "channels", summary.tts["channels"]),
                ("IFLYTEK_TTS_BIT_DEPTH", "bit_depth", summary.tts["bit_depth"]),
                ("IFLYTEK_TTS_FRAME_SIZE", "frame_size", summary.tts["frame_size"]),
                ("IFLYTEK_TTS_SPEED", "speed", summary.tts["speed"]),
                ("IFLYTEK_TTS_VOLUME", "volume", summary.tts["volume"]),
                ("IFLYTEK_TTS_PITCH", "pitch", summary.tts["pitch"]),
            ):
                if env_key in env_values and extra_headers.get(field_name) != value:
                    extra_headers[field_name] = value
                    changed = True

        asr_keys = {
            "SPARKWEAVE_ASR_PROVIDER",
            "SPARKWEAVE_ASR_TIMEOUT",
            "IFLYTEK_ASR_APPID",
            "IFLYTEK_ASR_API_KEY",
            "IFLYTEK_ASR_API_SECRET",
            "IFLYTEK_ASR_URL",
            "IFLYTEK_ASR_LANGUAGE",
            "IFLYTEK_ASR_ACCENT",
            "IFLYTEK_ASR_DOMAIN",
            "IFLYTEK_ASR_VAD_EOS",
        }
        if asr_keys.intersection(env_values) and can_sync_service("asr", "asr-profile-default"):
            profile = ensure_asr_profile()
            extra_headers = profile.setdefault("extra_headers", {})
            for env_key, field_name, value in (
                ("SPARKWEAVE_ASR_PROVIDER", "provider", summary.asr["provider"]),
                ("SPARKWEAVE_ASR_TIMEOUT", "timeout", summary.asr["timeout"]),
                ("IFLYTEK_ASR_API_KEY", "api_key", summary.asr["api_key"]),
                ("IFLYTEK_ASR_URL", "base_url", summary.asr["url"]),
            ):
                if env_key in env_values and profile.get(field_name) != value:
                    profile[field_name] = value
                    changed = True
            for env_key, field_name, value in (
                ("IFLYTEK_ASR_APPID", "app_id", summary.asr["app_id"]),
                ("IFLYTEK_ASR_API_SECRET", "api_secret", summary.asr["api_secret"]),
                ("IFLYTEK_ASR_LANGUAGE", "language", summary.asr["language"]),
                ("IFLYTEK_ASR_ACCENT", "accent", summary.asr["accent"]),
                ("IFLYTEK_ASR_DOMAIN", "domain", summary.asr["domain"]),
                ("IFLYTEK_ASR_VAD_EOS", "vad_eos", summary.asr["vad_eos"]),
            ):
                if env_key in env_values and extra_headers.get(field_name) != value:
                    extra_headers[field_name] = value
                    changed = True

        speech_eval_keys = {
            "SPARKWEAVE_SPEECH_EVAL_PROVIDER",
            "SPARKWEAVE_SPEECH_EVAL_TIMEOUT",
            "IFLYTEK_SPEECH_EVAL_APPID",
            "IFLYTEK_SPEECH_EVAL_API_KEY",
            "IFLYTEK_SPEECH_EVAL_API_SECRET",
            "IFLYTEK_SPEECH_EVAL_URL",
            "IFLYTEK_SPEECH_EVAL_CATEGORY",
            "IFLYTEK_SPEECH_EVAL_LANGUAGE",
        }
        if speech_eval_keys.intersection(env_values) and can_sync_service(
            "speech_eval",
            "speech-eval-profile-default",
        ):
            profile = ensure_speech_eval_profile()
            extra_headers = profile.setdefault("extra_headers", {})
            for env_key, field_name, value in (
                ("SPARKWEAVE_SPEECH_EVAL_PROVIDER", "provider", summary.speech_eval["provider"]),
                ("SPARKWEAVE_SPEECH_EVAL_TIMEOUT", "timeout", summary.speech_eval["timeout"]),
                ("IFLYTEK_SPEECH_EVAL_API_KEY", "api_key", summary.speech_eval["api_key"]),
                ("IFLYTEK_SPEECH_EVAL_URL", "base_url", summary.speech_eval["url"]),
            ):
                if env_key in env_values and profile.get(field_name) != value:
                    profile[field_name] = value
                    changed = True
            for env_key, field_name, value in (
                ("IFLYTEK_SPEECH_EVAL_APPID", "app_id", summary.speech_eval["app_id"]),
                ("IFLYTEK_SPEECH_EVAL_API_SECRET", "api_secret", summary.speech_eval["api_secret"]),
                ("IFLYTEK_SPEECH_EVAL_CATEGORY", "category", summary.speech_eval["category"]),
                ("IFLYTEK_SPEECH_EVAL_LANGUAGE", "language", summary.speech_eval["language"]),
            ):
                if env_key in env_values and extra_headers.get(field_name) != value:
                    extra_headers[field_name] = value
                    changed = True

        return changed

    def _sync_provider_credentials(self, catalog: dict[str, Any]) -> bool:
        """Move provider-owned credentials to one shared catalog location.

        The UI exposes these shared credentials once per provider. Service
        profiles keep routing/model fields, while runtime rendering fans the
        shared credentials back out to legacy env keys.
        """
        changed = False
        services = catalog.setdefault("services", {})
        credentials = catalog.setdefault("provider_credentials", {})
        defaults = _provider_credentials_shell()

        for provider, default_values in defaults.items():
            provider_values = credentials.setdefault(provider, {})
            for key, value in default_values.items():
                if key not in provider_values:
                    provider_values[key] = value
                    changed = True

        iflytek = credentials["iflytek"]
        siliconflow = credentials["siliconflow"]
        env = get_env_store().load()

        def set_if_empty(target: dict[str, Any], key: str, value: Any) -> None:
            nonlocal changed
            parsed = _as_str(value)
            if parsed and not _as_str(target.get(key)):
                target[key] = parsed
                changed = True

        def split_ak_sk(value: str) -> tuple[str, str]:
            if ":" not in value:
                return "", ""
            api_key, api_secret = value.split(":", 1)
            return api_key.strip(), api_secret.strip()

        set_if_empty(
            iflytek,
            "app_id",
            env.get("IFLYTEK_APPID")
            or env.get("IFLYTEK_OCR_APPID")
            or env.get("IFLYTEK_TTS_APPID")
            or env.get("IFLYTEK_EMBEDDING_APPID")
            or env.get("IFLYTEK_ASR_APPID")
            or env.get("IFLYTEK_SPEECH_EVAL_APPID")
            or env.get("IFLYTEK_FORMULA_APPID")
            or env.get("IFLYTEK_VISION_APPID"),
        )
        set_if_empty(
            iflytek,
            "api_key",
            env.get("IFLYTEK_API_KEY")
            or env.get("IFLYTEK_OCR_API_KEY")
            or env.get("IFLYTEK_TTS_API_KEY")
            or env.get("IFLYTEK_EMBEDDING_API_KEY")
            or env.get("IFLYTEK_ASR_API_KEY")
            or env.get("IFLYTEK_SPEECH_EVAL_API_KEY")
            or env.get("IFLYTEK_FORMULA_API_KEY")
            or env.get("IFLYTEK_VISION_API_KEY"),
        )
        set_if_empty(
            iflytek,
            "api_secret",
            env.get("IFLYTEK_API_SECRET")
            or env.get("IFLYTEK_OCR_API_SECRET")
            or env.get("IFLYTEK_TTS_API_SECRET")
            or env.get("IFLYTEK_EMBEDDING_API_SECRET")
            or env.get("IFLYTEK_ASR_API_SECRET")
            or env.get("IFLYTEK_SPEECH_EVAL_API_SECRET")
            or env.get("IFLYTEK_FORMULA_API_SECRET")
            or env.get("IFLYTEK_VISION_API_SECRET"),
        )
        set_if_empty(
            iflytek,
            "api_password",
            env.get("IFLYTEK_API_PASSWORD")
            or env.get("IFLYTEK_SPARK_API_PASSWORD")
            or env.get("IFLYTEK_SEARCH_API_PASSWORD"),
        )
        set_if_empty(
            siliconflow,
            "api_key",
            env.get("SILICONFLOW_API_KEY") or env.get("SILICONFLOW_OCR_API_KEY"),
        )

        def active_profile(service_name: str) -> dict[str, Any]:
            service = services.setdefault(
                service_name,
                _search_shell()
                if service_name == "search"
                else _ocr_shell()
                if service_name == "ocr"
                else _formula_ocr_shell()
                if service_name == "formula_ocr"
                else _image_understanding_shell()
                if service_name == "image_understanding"
                else _tts_shell()
                if service_name == "tts"
                else _asr_shell()
                if service_name == "asr"
                else _speech_eval_shell()
                if service_name == "speech_eval"
                else _service_shell(),
            )
            profiles = service.setdefault("profiles", [])
            profile = self.get_active_profile(catalog, service_name)
            return profile or (profiles[0] if profiles else {})

        llm_profile = active_profile("llm")
        llm_binding = canonical_provider_name(_as_str(llm_profile.get("binding")))
        llm_key = _as_str(llm_profile.get("api_key"))
        if llm_binding == "iflytek_spark_ws":
            api_key, api_secret = split_ak_sk(llm_key)
            set_if_empty(iflytek, "api_key", api_key)
            set_if_empty(iflytek, "api_secret", api_secret)
            set_if_empty(iflytek, "api_password", llm_key if not api_key else "")
        elif llm_binding == "siliconflow":
            set_if_empty(siliconflow, "api_key", llm_key)

        embedding_profile = active_profile("embedding")
        embedding_binding = _canonical_embedding_provider_name(_as_str(embedding_profile.get("binding")))
        embedding_key = _as_str(embedding_profile.get("api_key"))
        embedding_extra = embedding_profile.get("extra_headers") or {}
        if embedding_binding == "iflytek_spark":
            set_if_empty(iflytek, "api_key", embedding_key)
            set_if_empty(iflytek, "app_id", embedding_extra.get("app_id"))
            set_if_empty(iflytek, "api_secret", embedding_extra.get("api_secret"))
        elif self._profile_uses_siliconflow(embedding_profile):
            set_if_empty(siliconflow, "api_key", embedding_key)

        search_profile = active_profile("search")
        if _as_str(search_profile.get("provider")).lower().replace("-", "_") == "iflytek_spark":
            search_key = _as_str(search_profile.get("api_key"))
            api_key, api_secret = split_ak_sk(search_key)
            set_if_empty(iflytek, "api_key", api_key)
            set_if_empty(iflytek, "api_secret", api_secret)
            set_if_empty(iflytek, "api_password", search_key if not api_key else "")

        ocr_profile = active_profile("ocr")
        ocr_provider = _as_str(ocr_profile.get("provider")).lower().replace("-", "_")
        ocr_extra = ocr_profile.get("extra_headers") or {}
        if ocr_provider in {"iflytek", "xfyun", "xunfei"}:
            set_if_empty(iflytek, "api_key", ocr_profile.get("api_key"))
            set_if_empty(iflytek, "app_id", ocr_extra.get("app_id"))
            set_if_empty(iflytek, "api_secret", ocr_extra.get("api_secret"))
        elif ocr_provider in {"siliconflow", "silicon_flow", "deepseekocr", "deepseek_ocr"}:
            set_if_empty(siliconflow, "api_key", ocr_profile.get("api_key"))

        formula_ocr_profile = active_profile("formula_ocr")
        formula_ocr_provider = _as_str(formula_ocr_profile.get("provider")).lower().replace("-", "_")
        formula_ocr_extra = formula_ocr_profile.get("extra_headers") or {}
        if formula_ocr_provider in {"iflytek", "xfyun", "xunfei"}:
            set_if_empty(iflytek, "api_key", formula_ocr_profile.get("api_key"))
            set_if_empty(iflytek, "app_id", formula_ocr_extra.get("app_id"))
            set_if_empty(iflytek, "api_secret", formula_ocr_extra.get("api_secret"))

        image_understanding_profile = active_profile("image_understanding")
        image_understanding_provider = _as_str(image_understanding_profile.get("provider")).lower().replace("-", "_")
        image_understanding_extra = image_understanding_profile.get("extra_headers") or {}
        if image_understanding_provider in {"iflytek", "xfyun", "xunfei"}:
            set_if_empty(iflytek, "api_key", image_understanding_profile.get("api_key"))
            set_if_empty(iflytek, "app_id", image_understanding_extra.get("app_id"))
            set_if_empty(iflytek, "api_secret", image_understanding_extra.get("api_secret"))

        tts_profile = active_profile("tts")
        tts_provider = _as_str(tts_profile.get("provider")).lower().replace("-", "_")
        tts_extra = tts_profile.get("extra_headers") or {}
        if tts_provider in {"iflytek", "xfyun", "xunfei"}:
            set_if_empty(iflytek, "api_key", tts_profile.get("api_key"))
            set_if_empty(iflytek, "app_id", tts_extra.get("app_id"))
            set_if_empty(iflytek, "api_secret", tts_extra.get("api_secret"))

        asr_profile = active_profile("asr")
        asr_provider = _as_str(asr_profile.get("provider")).lower().replace("-", "_")
        asr_extra = asr_profile.get("extra_headers") or {}
        if asr_provider in {"iflytek", "xfyun", "xunfei"}:
            set_if_empty(iflytek, "api_key", asr_profile.get("api_key"))
            set_if_empty(iflytek, "app_id", asr_extra.get("app_id"))
            set_if_empty(iflytek, "api_secret", asr_extra.get("api_secret"))

        speech_eval_profile = active_profile("speech_eval")
        speech_eval_provider = _as_str(speech_eval_profile.get("provider")).lower().replace("-", "_")
        speech_eval_extra = speech_eval_profile.get("extra_headers") or {}
        if speech_eval_provider in {"iflytek", "xfyun", "xunfei"}:
            set_if_empty(iflytek, "api_key", speech_eval_profile.get("api_key"))
            set_if_empty(iflytek, "app_id", speech_eval_extra.get("app_id"))
            set_if_empty(iflytek, "api_secret", speech_eval_extra.get("api_secret"))

        changed = self._strip_shared_credentials_from_profiles(catalog) or changed
        return changed

    def _profile_uses_siliconflow(self, profile: dict[str, Any] | None) -> bool:
        if not profile:
            return False
        binding = canonical_provider_name(_as_str(profile.get("binding")))
        provider = _as_str(profile.get("provider")).lower().replace("-", "_")
        base_url = _as_str(profile.get("base_url")).lower()
        return binding == "siliconflow" or provider == "siliconflow" or "siliconflow" in base_url

    def _strip_shared_credentials_from_profiles(self, catalog: dict[str, Any]) -> bool:
        changed = False
        credentials = catalog.setdefault("provider_credentials", _provider_credentials_shell())
        iflytek = credentials.get("iflytek") or {}
        siliconflow = credentials.get("siliconflow") or {}
        has_iflytek = any(_as_str(iflytek.get(key)) for key in ("app_id", "api_key", "api_secret", "api_password"))
        has_siliconflow = bool(_as_str(siliconflow.get("api_key")))
        services = catalog.setdefault("services", {})

        def same_non_empty(value: Any, candidate: Any) -> bool:
            parsed = _as_str(value)
            target = _as_str(candidate)
            return bool(parsed and target and parsed == target)

        iflytek_key_candidates = [
            iflytek.get("api_key"),
            iflytek.get("api_password"),
            (
                f"{_as_str(iflytek.get('api_key'))}:{_as_str(iflytek.get('api_secret'))}"
                if _as_str(iflytek.get("api_key")) and _as_str(iflytek.get("api_secret"))
                else ""
            ),
        ]

        def clear_profile_key(profile: dict[str, Any], *candidates: Any) -> None:
            nonlocal changed
            if any(same_non_empty(profile.get("api_key"), candidate) for candidate in candidates):
                profile["api_key"] = ""
                changed = True

        def clear_extra(profile: dict[str, Any], *pairs: tuple[str, Any]) -> None:
            nonlocal changed
            extra = profile.setdefault("extra_headers", {})
            for key, candidate in pairs:
                if same_non_empty(extra.get(key), candidate):
                    extra[key] = ""
                    changed = True

        for profile in services.get("llm", {}).get("profiles", []):
            if canonical_provider_name(_as_str(profile.get("binding"))) == "iflytek_spark_ws" and has_iflytek:
                clear_profile_key(profile, *iflytek_key_candidates)
                clear_extra(
                    profile,
                    ("app_id", iflytek.get("app_id")),
                    ("appid", iflytek.get("app_id")),
                    ("api_secret", iflytek.get("api_secret")),
                )
            elif self._profile_uses_siliconflow(profile) and has_siliconflow:
                clear_profile_key(profile, siliconflow.get("api_key"))

        for profile in services.get("embedding", {}).get("profiles", []):
            binding = _canonical_embedding_provider_name(_as_str(profile.get("binding")))
            if binding == "iflytek_spark" and has_iflytek:
                clear_profile_key(profile, iflytek.get("api_key"))
                clear_extra(profile, ("app_id", iflytek.get("app_id")), ("api_secret", iflytek.get("api_secret")))
            elif self._profile_uses_siliconflow(profile) and has_siliconflow:
                clear_profile_key(profile, siliconflow.get("api_key"))

        for profile in services.get("search", {}).get("profiles", []):
            provider = _as_str(profile.get("provider")).lower().replace("-", "_")
            if provider == "iflytek_spark" and has_iflytek:
                clear_profile_key(profile, *iflytek_key_candidates)

        for profile in services.get("ocr", {}).get("profiles", []):
            provider = _as_str(profile.get("provider")).lower().replace("-", "_")
            if provider in {"iflytek", "xfyun", "xunfei"} and has_iflytek:
                clear_profile_key(profile, iflytek.get("api_key"))
                clear_extra(profile, ("app_id", iflytek.get("app_id")), ("api_secret", iflytek.get("api_secret")))
            elif provider in {"siliconflow", "silicon_flow", "deepseekocr", "deepseek_ocr"} and has_siliconflow:
                clear_profile_key(profile, siliconflow.get("api_key"))

        for service_name in ("formula_ocr", "image_understanding"):
            for profile in services.get(service_name, {}).get("profiles", []):
                provider = _as_str(profile.get("provider")).lower().replace("-", "_")
                if provider in {"iflytek", "xfyun", "xunfei"} and has_iflytek:
                    clear_profile_key(profile, iflytek.get("api_key"))
                    clear_extra(profile, ("app_id", iflytek.get("app_id")), ("api_secret", iflytek.get("api_secret")))

        for profile in services.get("tts", {}).get("profiles", []):
            provider = _as_str(profile.get("provider")).lower().replace("-", "_")
            if provider in {"iflytek", "xfyun", "xunfei"} and has_iflytek:
                clear_profile_key(profile, iflytek.get("api_key"))
                clear_extra(profile, ("app_id", iflytek.get("app_id")), ("api_secret", iflytek.get("api_secret")))

        for profile in services.get("asr", {}).get("profiles", []):
            provider = _as_str(profile.get("provider")).lower().replace("-", "_")
            if provider in {"iflytek", "xfyun", "xunfei"} and has_iflytek:
                clear_profile_key(profile, iflytek.get("api_key"))
                clear_extra(profile, ("app_id", iflytek.get("app_id")), ("api_secret", iflytek.get("api_secret")))

        for profile in services.get("speech_eval", {}).get("profiles", []):
            provider = _as_str(profile.get("provider")).lower().replace("-", "_")
            if provider in {"iflytek", "xfyun", "xunfei"} and has_iflytek:
                clear_profile_key(profile, iflytek.get("api_key"))
                clear_extra(profile, ("app_id", iflytek.get("app_id")), ("api_secret", iflytek.get("api_secret")))

        return changed

    def get_active_profile(self, catalog: dict[str, Any], service_name: str) -> dict[str, Any] | None:
        service = catalog.get("services", {}).get(service_name, {})
        active_id = service.get("active_profile_id")
        for profile in service.get("profiles", []):
            if profile.get("id") == active_id:
                return profile
        profiles = service.get("profiles", [])
        return profiles[0] if profiles else None

    def get_active_model(self, catalog: dict[str, Any], service_name: str) -> dict[str, Any] | None:
        if service_name == "search":
            return None
        service = catalog.get("services", {}).get(service_name, {})
        active_model_id = service.get("active_model_id")
        profile = self.get_active_profile(catalog, service_name)
        if not profile:
            return None
        for model in profile.get("models", []):
            if model.get("id") == active_model_id:
                return model
        models = profile.get("models", [])
        return models[0] if models else None

    def _normalize(self, catalog: dict[str, Any]) -> None:
        services = catalog.setdefault("services", {})
        services.setdefault("llm", _service_shell())
        services.setdefault("embedding", _service_shell())
        services.setdefault("search", _search_shell())
        services.setdefault("ocr", _ocr_shell())
        services.setdefault("formula_ocr", _formula_ocr_shell())
        services.setdefault("image_understanding", _image_understanding_shell())
        services.setdefault("tts", _tts_shell())
        services.setdefault("asr", _asr_shell())
        services.setdefault("speech_eval", _speech_eval_shell())
        for service_name in (
            "llm",
            "embedding",
            "search",
            "ocr",
            "formula_ocr",
            "image_understanding",
            "tts",
            "asr",
            "speech_eval",
        ):
            service = services[service_name]
            profiles = service.setdefault("profiles", [])
            for profile in profiles:
                profile.setdefault("id", f"{service_name}-profile-{uuid4().hex[:8]}")
                profile.setdefault("name", "Untitled Profile")
                profile.setdefault("api_version", "")
                profile.setdefault("base_url", "")
                profile.setdefault("api_key", "")
                if service_name == "search":
                    profile.setdefault("provider", "brave")
                    profile.setdefault("proxy", "")
                    profile["models"] = []
                elif service_name == "ocr":
                    profile.setdefault("provider", "iflytek")
                    profile.setdefault("strategy", "auto")
                    ocr_provider = str(profile.get("provider") or "iflytek").strip().lower().replace("-", "_")
                    if ocr_provider in {"siliconflow", "silicon_flow", "deepseekocr", "deepseek_ocr"}:
                        profile.setdefault("base_url", DEFAULT_SILICONFLOW_OCR_BASE_URL)
                    else:
                        profile.setdefault("base_url", DEFAULT_IFLYTEK_OCR_URL)
                    extra_headers = profile.setdefault("extra_headers", {})
                    extra_headers.setdefault("app_id", "")
                    extra_headers.setdefault("api_secret", "")
                    extra_headers.setdefault("service_id", DEFAULT_IFLYTEK_OCR_SERVICE_ID)
                    extra_headers.setdefault("category", DEFAULT_IFLYTEK_OCR_CATEGORY)
                    extra_headers.setdefault("model", DEFAULT_SILICONFLOW_OCR_MODEL)
                    extra_headers.setdefault("prompt", DEFAULT_SILICONFLOW_OCR_PROMPT)
                    profile["models"] = []
                elif service_name == "formula_ocr":
                    profile.setdefault("provider", "iflytek")
                    profile.setdefault("base_url", DEFAULT_IFLYTEK_FORMULA_URL)
                    profile.setdefault("timeout", "30")
                    extra_headers = profile.setdefault("extra_headers", {})
                    extra_headers.setdefault("app_id", "")
                    extra_headers.setdefault("api_secret", "")
                    extra_headers.setdefault("ent", DEFAULT_IFLYTEK_FORMULA_ENT)
                    extra_headers.setdefault("aue", DEFAULT_IFLYTEK_FORMULA_AUE)
                    profile["models"] = []
                elif service_name == "image_understanding":
                    profile.setdefault("provider", "iflytek")
                    profile.setdefault("base_url", DEFAULT_IFLYTEK_VISION_URL)
                    profile.setdefault("timeout", "45")
                    extra_headers = profile.setdefault("extra_headers", {})
                    extra_headers.setdefault("app_id", "")
                    extra_headers.setdefault("api_secret", "")
                    extra_headers.setdefault("protocol", DEFAULT_IFLYTEK_VISION_PROTOCOL)
                    extra_headers.setdefault("domain", DEFAULT_IFLYTEK_VISION_DOMAIN)
                    extra_headers.setdefault("max_tokens", "2048")
                    extra_headers.setdefault("temperature", "0.2")
                    extra_headers.setdefault("top_k", "4")
                    extra_headers.setdefault("uid", "sparkweave")
                    profile["models"] = []
                elif service_name == "tts":
                    profile.setdefault("provider", "iflytek")
                    profile.setdefault("base_url", DEFAULT_IFLYTEK_TTS_URL)
                    profile.setdefault("timeout", "30")
                    extra_headers = profile.setdefault("extra_headers", {})
                    extra_headers.setdefault("app_id", "")
                    extra_headers.setdefault("api_secret", "")
                    extra_headers.setdefault("voice", DEFAULT_IFLYTEK_TTS_VOICE)
                    extra_headers.setdefault("encoding", "lame")
                    extra_headers.setdefault("sample_rate", "24000")
                    extra_headers.setdefault("channels", "1")
                    extra_headers.setdefault("bit_depth", "16")
                    extra_headers.setdefault("frame_size", "0")
                    extra_headers.setdefault("speed", "50")
                    extra_headers.setdefault("volume", "50")
                    extra_headers.setdefault("pitch", "50")
                    profile["models"] = []
                elif service_name == "asr":
                    profile.setdefault("provider", "iflytek")
                    profile.setdefault("base_url", DEFAULT_IFLYTEK_ASR_URL)
                    profile.setdefault("timeout", "60")
                    extra_headers = profile.setdefault("extra_headers", {})
                    extra_headers.setdefault("app_id", "")
                    extra_headers.setdefault("api_secret", "")
                    extra_headers.setdefault("language", "zh_cn")
                    extra_headers.setdefault("accent", "mandarin")
                    extra_headers.setdefault("domain", "iat")
                    extra_headers.setdefault("vad_eos", "3000")
                    profile["models"] = []
                elif service_name == "speech_eval":
                    profile.setdefault("provider", "iflytek")
                    profile.setdefault("base_url", DEFAULT_IFLYTEK_SPEECH_EVAL_URL)
                    profile.setdefault("timeout", "60")
                    extra_headers = profile.setdefault("extra_headers", {})
                    extra_headers.setdefault("app_id", "")
                    extra_headers.setdefault("api_secret", "")
                    extra_headers.setdefault("category", "read_sentence")
                    extra_headers.setdefault("language", "zh_cn")
                    profile["models"] = []
                else:
                    profile.setdefault("binding", "openai")
                    llm_spec = None
                    legacy_iflytek_hint: str | None = None
                    if service_name == "llm":
                        raw_binding = _as_str(profile.get("binding")).lower().replace("-", "_")
                        if _is_iflytek_x2_alias(raw_binding):
                            legacy_iflytek_hint = "x2"
                        elif _is_iflytek_x15_alias(raw_binding):
                            legacy_iflytek_hint = "x1.5"
                        canonical = canonical_provider_name(_as_str(profile.get("binding")))
                        if canonical and any(spec.name == canonical for spec in PROVIDERS):
                            profile["binding"] = canonical
                            llm_spec = find_by_name(canonical)
                        if llm_spec and llm_spec.name == "iflytek_spark_ws":
                            base_url = _as_str(profile.get("base_url"))
                            selected_model = ((profile.get("models") or [{}])[0] or {}).get(
                                "model"
                            )
                            profile["base_url"] = _iflytek_ws_default_base(
                                legacy_iflytek_hint or selected_model,
                                base_url,
                                profile.get("binding"),
                            )
                    profile.setdefault("extra_headers", {})
                    models = profile.setdefault("models", [])
                    for model in models:
                        model.setdefault("id", f"{service_name}-model-{uuid4().hex[:8]}")
                        model.setdefault("name", model.get("model") or "Untitled Model")
                        model.setdefault("model", "")
                        if service_name == "llm" and llm_spec and llm_spec.name == "iflytek_spark_ws":
                            normalized_model = _normalize_iflytek_ws_model(
                                model.get("model"),
                                profile.get("base_url"),
                                profile.get("binding"),
                            )
                            model["name"] = normalized_model
                            model["model"] = normalized_model
                        if service_name == "embedding":
                            model.setdefault("dimension", "3072")
            if profiles and not service.get("active_profile_id"):
                service["active_profile_id"] = profiles[0].get("id")
            if service_name in {"llm", "embedding"} and not service.get("active_model_id"):
                active_profile = self.get_active_profile(catalog, service_name)
                models = (active_profile or {}).get("models", [])
                if models:
                    service["active_model_id"] = models[0].get("id")


def get_model_catalog_service() -> ModelCatalogService:
    return ModelCatalogService.get_instance()


def get_config_test_runner():
    """Return the NG streamed config-test runner without importing it eagerly."""
    from sparkweave.services.config_test_runner import get_config_test_runner as _get_runner

    return _get_runner()


def get_kb_config_service():
    """Return the NG knowledge-base config service without importing it eagerly."""
    from sparkweave.services.kb_config import get_kb_config_service as _get_service

    return _get_service()


def get_runtime_settings_dir(project_root: Path | None = None) -> Path:
    """Return the canonical runtime settings directory."""
    root = project_root or PROJECT_ROOT
    return root / "data" / "user" / "settings"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_yaml_file(file_path: Path) -> dict[str, Any]:
    with open(file_path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


async def _load_yaml_file_async(file_path: Path) -> dict[str, Any]:
    return await asyncio.to_thread(_load_yaml_file, file_path)


def _config_path(path: Path) -> str:
    return path.as_posix()


def _inject_runtime_paths(config: dict[str, Any]) -> dict[str, Any]:
    """Expose canonical runtime paths without storing them as user-editable YAML."""
    path_service = get_path_service()
    normalized = dict(config or {})
    tools = dict(normalized.get("tools", {}) or {})
    run_code = dict(tools.get("run_code", {}) or {})
    run_code["workspace"] = _config_path(path_service.get_chat_feature_dir("_detached_code_execution"))
    tools["run_code"] = run_code
    normalized["tools"] = tools
    normalized["paths"] = {
        "user_data_dir": _config_path(path_service.get_user_root()),
        "knowledge_bases_dir": _config_path(path_service.project_root / "data" / "knowledge_bases"),
        "user_log_dir": _config_path(path_service.get_logs_dir()),
        "performance_log_dir": _config_path(path_service.get_logs_dir() / "performance"),
        "guide_output_dir": _config_path(path_service.get_guide_dir()),
        "question_output_dir": _config_path(path_service.get_chat_feature_dir("deep_question")),
        "research_output_dir": _config_path(path_service.get_research_dir()),
        "research_reports_dir": _config_path(path_service.get_research_reports_dir()),
        "solve_output_dir": _config_path(path_service.get_chat_feature_dir("deep_solve")),
    }
    return normalized


def _load_config_data(config_file: str, config_path: Path, project_root: Path) -> dict[str, Any]:
    main_path = get_runtime_settings_dir(project_root) / "main.yaml"
    config_data = _load_yaml_file(config_path)
    if config_file == "main.yaml" or not main_path.exists() or main_path == config_path:
        return config_data
    return _deep_merge(_load_yaml_file(main_path), config_data)


def resolve_config_path(
    config_file: str,
    project_root: Path | None = None,
) -> tuple[Path, bool]:
    """Resolve *config_file* inside ``data/user/settings``."""
    root = project_root or PROJECT_ROOT
    path = get_runtime_settings_dir(root) / config_file
    if path.exists():
        return path, False
    raise FileNotFoundError(f"Configuration file not found: {config_file} (expected under {path.parent})")


def load_config_with_main(config_file: str, project_root: Path | None = None) -> dict[str, Any]:
    """Load a runtime YAML config and merge it with ``main.yaml`` when needed."""
    root = project_root or PROJECT_ROOT
    config_path, _ = resolve_config_path(config_file, root)
    return _inject_runtime_paths(_load_config_data(config_file, config_path, root))


async def load_config_with_main_async(
    config_file: str,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Async wrapper for loading runtime YAML config plus injected paths."""
    root = project_root or PROJECT_ROOT
    config_path, _ = resolve_config_path(config_file, root)
    main_path = get_runtime_settings_dir(root) / "main.yaml"
    config_data = await _load_yaml_file_async(config_path)
    if config_file != "main.yaml" and main_path.exists() and main_path != config_path:
        config_data = _deep_merge(await _load_yaml_file_async(main_path), config_data)
    return _inject_runtime_paths(config_data)


def get_path_from_config(config: dict[str, Any], path_key: str, default: str | None = None) -> str | None:
    """Get a canonical runtime path from an already loaded config dictionary."""
    injected = _inject_runtime_paths(config)
    paths = injected.get("paths", {})
    if isinstance(paths, dict) and path_key in paths:
        return paths[path_key]
    if path_key == "workspace":
        return injected.get("tools", {}).get("run_code", {}).get("workspace", default)
    return default


def parse_language(language: Any) -> str:
    """Normalize language configuration to ``zh`` or ``en``."""
    if not language:
        return "zh"
    if isinstance(language, str):
        lang_lower = language.lower()
        if lang_lower in ["en", "english", "eng"]:
            return "en"
        if lang_lower in ["zh", "chinese", "cn", "中文", "汉语"]:
            return "zh"
    return "zh"


def get_agent_params(module_name: str) -> dict[str, Any]:
    """Return temperature/max-token settings from runtime ``agents.yaml``."""
    defaults = {
        "temperature": 0.5,
        "max_tokens": 4096,
    }
    section_map = {
        "solve": ("capabilities", "solve"),
        "research": ("capabilities", "research"),
        "question": ("capabilities", "question"),
        "guide": ("capabilities", "guide"),
        "co_writer": ("capabilities", "co_writer"),
        "brainstorm": ("tools", "brainstorm"),
        "vision_solver": ("plugins", "vision_solver"),
        "math_animator": ("plugins", "math_animator"),
        "llm_probe": ("diagnostics", "llm_probe"),
    }
    section = section_map.get(module_name)
    if section is None:
        return dict(defaults)

    agents_config = load_config_with_main("agents.yaml")
    module_config: dict[str, Any] = agents_config
    for key in section:
        value = module_config.get(key, {})
        module_config = value if isinstance(value, dict) else {}
    return {
        "temperature": module_config.get("temperature", defaults["temperature"]),
        "max_tokens": module_config.get("max_tokens", defaults["max_tokens"]),
    }


@dataclass(slots=True)
class NormalizedProviderConfig:
    name: str
    api_key: str = ""
    api_base: str | None = None
    api_version: str | None = None
    extra_headers: dict[str, str] | None = None


@dataclass(slots=True)
class ResolvedLLMConfig:
    model: str
    provider_name: str
    provider_mode: str
    binding_hint: str | None = None
    binding: str = "openai"
    api_key: str = ""
    base_url: str | None = None
    effective_url: str | None = None
    api_version: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)
    reasoning_effort: str | None = None


@dataclass(slots=True)
class ResolvedEmbeddingConfig:
    """Resolved runtime embedding config."""

    model: str
    provider_name: str
    provider_mode: str
    binding_hint: str | None = None
    binding: str = "openai"
    api_key: str = ""
    base_url: str | None = None
    effective_url: str | None = None
    api_version: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)
    dimension: int = 3072
    request_timeout: int = 60
    batch_size: int = 10
    batch_delay: float = 0.0


@dataclass(slots=True)
class ResolvedSearchConfig:
    """Resolved runtime web-search config."""

    provider: str
    requested_provider: str
    api_key: str = ""
    base_url: str = ""
    max_results: int = 5
    proxy: str | None = None
    unsupported_provider: bool = False
    deprecated_provider: bool = False
    missing_credentials: bool = False
    fallback_reason: str | None = None

    @property
    def status(self) -> str:
        if self.unsupported_provider:
            return "unsupported"
        if self.deprecated_provider:
            return "deprecated"
        if self.missing_credentials:
            return "missing_credentials"
        if self.fallback_reason:
            return "fallback"
        return "ok"


class LLMConfigUpdate(TypedDict, total=False):
    """Fields allowed when cloning an LLMConfig instance."""

    model: str
    api_key: str
    base_url: str | None
    effective_url: str | None
    binding: str
    provider_name: str
    provider_mode: str
    api_version: str | None
    extra_headers: dict[str, str]
    reasoning_effort: str | None
    max_tokens: int
    temperature: float
    max_concurrency: int
    requests_per_minute: int
    traffic_controller: Any | None


@dataclass
class LLMConfig:
    """Runtime LLM configuration used by NG services."""

    model: str
    api_key: str
    base_url: str | None = None
    effective_url: str | None = None
    binding: str = "openai"
    provider_name: str = "openai"
    provider_mode: str = "standard"
    api_version: str | None = None
    extra_headers: dict[str, str] | None = None
    reasoning_effort: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.7
    max_concurrency: int = 20
    requests_per_minute: int = 600
    traffic_controller: Any | None = None

    def __post_init__(self) -> None:
        if self.effective_url is None:
            self.effective_url = self.base_url

    def model_copy(self, update: LLMConfigUpdate | None = None) -> "LLMConfig":
        """Return a copy of the config with optional updates."""
        return replace(self, **(update or {}))

    def get_api_key(self) -> str:
        """Return the API key string for provider consumers."""
        return self.api_key


def _as_str(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _strip_value(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().strip("\"'")


def _to_headers(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items() if str(k).strip() and v is not None}
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items() if str(k).strip() and v is not None}
    return {}


def _is_local_base_url(base_url: str | None) -> bool:
    if not base_url:
        return False
    try:
        parsed = urlparse(base_url if "://" in base_url else f"http://{base_url}")
    except Exception:
        return False
    host = (parsed.hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local")


def _load_catalog(catalog: dict[str, Any] | None) -> dict[str, Any]:
    if catalog is not None:
        return catalog
    return get_model_catalog_service().load()


def _collect_provider_pool(catalog: dict[str, Any]) -> dict[str, NormalizedProviderConfig]:
    providers: dict[str, NormalizedProviderConfig] = {}
    llm_profiles = catalog.get("services", {}).get("llm", {}).get("profiles", [])
    for profile in llm_profiles:
        name = canonical_provider_name(_as_str(profile.get("binding")))
        if not name:
            continue
        providers[name] = NormalizedProviderConfig(
            name=name,
            api_key=_as_str(profile.get("api_key")),
            api_base=_as_str(profile.get("base_url")) or None,
            api_version=_as_str(profile.get("api_version")) or None,
            extra_headers=_to_headers(profile.get("extra_headers")) or None,
        )
    return providers


def _llm_provider_env_key(spec: ProviderSpec, env: EnvStore) -> str:
    """Return a provider-specific LLM credential when the generic key is empty."""
    env_names = [spec.env_key] if spec.env_key else []
    if spec.name == "iflytek_spark_ws":
        env_names.extend(
            [
                "IFLYTEK_API_PASSWORD",
                "IFLYTEK_SPARK_API_PASSWORD",
                "IFLYTEK_API_KEY",
                "IFLYTEK_SPARK_API_KEY",
                "XFYUN_SPARK_API_PASSWORD",
                "XFYUN_SPARK_API_KEY",
                "IFLYTEK_SPARK_WS_API_KEY",
                "IFLYTEK_WS_API_KEY",
                "XFYUN_WS_API_KEY",
                "SPARK_WS_API_KEY",
            ]
        )
    elif spec.name == "iflytek_maas_coding":
        env_names.extend(
            [
                "IFLYTEK_MAAS_CODING_API_PASSWORD",
                "IFLYTEK_MAAS_CODING_API_KEY",
                "XFYUN_MAAS_CODING_API_PASSWORD",
                "XFYUN_MAAS_CODING_API_KEY",
                "ASTRON_CODE_API_PASSWORD",
                "ASTRON_CODE_API_KEY",
            ]
        )
    elif spec.name == "siliconflow":
        env_names.insert(0, "SILICONFLOW_API_KEY")
    for key in env_names:
        value = env.get(key, "").strip()
        if value:
            return value
    return ""


def _iflytek_ws_env(env: EnvStore) -> dict[str, str]:
    values: dict[str, str] = {}
    candidates = {
        "app_id": (
            "IFLYTEK_SPARK_WS_APPID",
            "IFLYTEK_SPARK_WS_APP_ID",
            "IFLYTEK_WS_APPID",
            "IFLYTEK_APPID",
            "XFYUN_WS_APPID",
            "SPARK_WS_APPID",
        ),
        "api_secret": (
            "IFLYTEK_SPARK_WS_API_SECRET",
            "IFLYTEK_WS_API_SECRET",
            "XFYUN_WS_API_SECRET",
            "SPARK_WS_API_SECRET",
        ),
        "domain": (
            "IFLYTEK_SPARK_WS_DOMAIN",
            "IFLYTEK_WS_DOMAIN",
            "SPARK_WS_DOMAIN",
        ),
    }
    for field_name, env_names in candidates.items():
        for env_name in env_names:
            value = env.get(env_name, "").strip()
            if value:
                values[field_name] = value
                break
    return values


def _iflytek_ws_default_base(
    model: str | None,
    base_url: str | None = "",
    binding_hint: str | None = "",
) -> str:
    return _iflytek_spark_default_base(model, base_url, binding_hint)


def _normalize_iflytek_ws_model(
    model: str | None,
    base_url: str | None = "",
    binding_hint: str | None = "",
) -> str:
    """Keep iFlytek OpenAI-compatible runtime on the official Spark-X model id."""
    del model, base_url, binding_hint
    return IFLYTEK_SPARK_MODEL


def _iflytek_spark_default_base(
    model: str | None = "",
    base_url: str | None = "",
    binding_hint: str | None = "",
) -> str:
    """Resolve X2/X1.5 by base URL or legacy aliases while keeping model=spark-x."""
    key = (model or "").strip().lower()
    binding_key = (binding_hint or "").strip().lower()
    base_lower = (base_url or "").strip().lower()
    if (
        key in {"spark-x1.5", "spark-x15", "x1.5", "x15"}
        or _is_iflytek_x15_alias(binding_key)
        or "/v1/x1" in base_lower
        or "spark-api-open.xf-yun.com/v2" in base_lower
        or base_lower.rstrip("/").endswith("/v2")
    ):
        return IFLYTEK_SPARK_X15_BASE_URL
    return IFLYTEK_SPARK_X2_BASE_URL


def _is_iflytek_ws_supported_base_url(base_url: str | None) -> bool:
    value = (base_url or "").strip().lower()
    if not value.startswith("https://spark-api-open.xf-yun.com/"):
        return False
    return value.rstrip("/").endswith(("/x2", "/v2"))


def _is_iflytek_x2_alias(value: str | None) -> bool:
    key = (value or "").strip().lower().replace("-", "_")
    return key in {"iflytek_spark_x2", "spark_x2", "iflytek_x2", "xfyun_x2", "xunfei_x2", "x2"}


def _is_iflytek_x15_alias(value: str | None) -> bool:
    key = (value or "").strip().lower().replace("-", "_")
    return key in {
        "iflytek_spark_x15",
        "spark_x15",
        "spark_x1_5",
        "iflytek_x15",
        "iflytek_x1_5",
        "xfyun_x15",
        "xfyun_x1_5",
        "xunfei_x15",
        "xunfei_x1_5",
        "x15",
        "x1_5",
        "x1.5",
    }


def _choose_resolved_provider(
    *,
    hint: str | None,
    model: str,
    api_key: str,
    api_base: str | None,
    provider_pool: dict[str, NormalizedProviderConfig],
) -> ProviderSpec:
    explicit_spec = find_by_name(hint) if hint else None
    detected_gateway = find_gateway(api_key=api_key or None, api_base=api_base or None)
    if explicit_spec and detected_gateway and explicit_spec.name == "openai":
        return detected_gateway
    if explicit_spec:
        return explicit_spec
    if detected_gateway:
        return detected_gateway

    model_spec = find_by_model(model)
    if model_spec:
        return model_spec

    if _is_local_base_url(api_base):
        if api_base and "11434" in api_base:
            return find_by_name("ollama") or find_by_name("vllm") or find_by_name("openai")
        return find_by_name("vllm") or find_by_name("ollama") or find_by_name("openai")

    for spec in PROVIDERS:
        configured = provider_pool.get(spec.name)
        if not configured:
            continue
        if spec.is_gateway and (configured.api_key or configured.api_base):
            return spec
    for spec in PROVIDERS:
        configured = provider_pool.get(spec.name)
        if not configured:
            continue
        if spec.is_local and configured.api_base:
            return spec
        if not spec.is_oauth and configured.api_key:
            return spec

    return find_by_name("openai") or PROVIDERS[0]


def resolve_llm_runtime_config(
    catalog: dict[str, Any] | None = None,
    *,
    env_store: EnvStore | None = None,
    service: ModelCatalogService | None = None,
) -> ResolvedLLMConfig:
    """Resolve active LLM config from model catalog plus `.env` fallback."""
    env = env_store or get_env_store()
    catalog_service = service or get_model_catalog_service()
    loaded = catalog if catalog is not None else catalog_service.load()

    profile = catalog_service.get_active_profile(loaded, "llm")
    model = catalog_service.get_active_model(loaded, "llm")
    summary = env.as_summary()
    env_values = env.load()

    resolved_model = _as_str((model or {}).get("model")) or summary.llm.get("model", "").strip()
    if not resolved_model:
        resolved_model = "gpt-5.4-mini"

    binding_hint_raw = _as_str((profile or {}).get("binding"))
    if not binding_hint_raw and "LLM_BINDING" in env_values:
        binding_hint_raw = _as_str(summary.llm.get("binding", ""))
    binding_hint = canonical_provider_name(binding_hint_raw)

    active_api_key = _as_str((profile or {}).get("api_key")) or summary.llm.get("api_key", "")
    active_api_base = _as_str((profile or {}).get("base_url")) or summary.llm.get("host", "")
    active_api_version = (
        _as_str((profile or {}).get("api_version")) or summary.llm.get("api_version", "")
    )
    active_extra_headers = _to_headers((profile or {}).get("extra_headers"))
    reasoning_effort = _as_str((model or {}).get("reasoning_effort")) or None

    provider_pool = _collect_provider_pool(loaded)
    spec = _choose_resolved_provider(
        hint=binding_hint,
        model=resolved_model,
        api_key=active_api_key,
        api_base=active_api_base or None,
        provider_pool=provider_pool,
    )

    mapped = provider_pool.get(spec.name)
    iflytek_model_hint = resolved_model
    if spec.name == "iflytek_spark_ws":
        resolved_model = _normalize_iflytek_ws_model(
            resolved_model,
            active_api_base,
            binding_hint_raw,
        )
    api_key = active_api_key or (mapped.api_key if mapped else "")
    if not api_key and not spec.is_local and not spec.is_oauth:
        api_key = _llm_provider_env_key(spec, env)
    api_base = active_api_base or ((mapped.api_base or "") if mapped else "")
    api_version = active_api_version or ((mapped.api_version or "") if mapped else "")
    if spec.name == "iflytek_spark_ws":
        api_base = _iflytek_ws_default_base(iflytek_model_hint, api_base, binding_hint_raw)
    elif not api_base and spec.default_api_base:
        api_base = spec.default_api_base
    if not api_key and spec.is_local:
        api_key = "sk-no-key-required"
    extra_headers = active_extra_headers or ((mapped.extra_headers or {}) if mapped else {})
    if spec.name == "iflytek_spark_ws":
        extra_headers = {
            key: value
            for key, value in extra_headers.items()
            if key.lower().replace("-", "_") not in {"app_id", "appid", "api_secret", "domain"}
        }

    return ResolvedLLMConfig(
        model=resolved_model,
        provider_name=spec.name,
        provider_mode=spec.mode,
        binding_hint=binding_hint,
        binding=spec.name,
        api_key=api_key,
        base_url=api_base or None,
        effective_url=api_base or None,
        api_version=api_version or None,
        extra_headers=extra_headers,
        reasoning_effort=reasoning_effort,
    )


def _canonical_embedding_provider_name(name: str | None) -> str | None:
    if not name:
        return None
    key = name.strip().replace("-", "_")
    if not key:
        return None
    key = EMBEDDING_PROVIDER_ALIASES.get(key, key)
    key = canonical_provider_name(key) or key
    key = EMBEDDING_PROVIDER_ALIASES.get(key, key)
    if key in EMBEDDING_PROVIDERS:
        return key
    return None


def _collect_embedding_provider_pool(catalog: dict[str, Any]) -> dict[str, NormalizedProviderConfig]:
    providers: dict[str, NormalizedProviderConfig] = {}
    embedding_profiles = catalog.get("services", {}).get("embedding", {}).get("profiles", [])
    for profile in embedding_profiles:
        name = _canonical_embedding_provider_name(_as_str(profile.get("binding")))
        if not name:
            continue
        providers[name] = NormalizedProviderConfig(
            name=name,
            api_key=_as_str(profile.get("api_key")),
            api_base=_as_str(profile.get("base_url")) or None,
            api_version=_as_str(profile.get("api_version")) or None,
            extra_headers=_to_headers(profile.get("extra_headers")) or None,
        )
    return providers


def _resolve_embedding_dimension(value: Any, default: int = 3072) -> int:
    try:
        parsed = int(str(value).strip())
        return max(1, parsed)
    except (TypeError, ValueError):
        return default


def _resolve_embedding_provider(
    *,
    hint: str | None,
    model: str,
    api_base: str | None,
    provider_pool: dict[str, NormalizedProviderConfig],
) -> str:
    if hint and hint in EMBEDDING_PROVIDERS:
        return hint

    model_lower = (model or "").lower()
    model_prefix = model_lower.split("/", 1)[0].replace("-", "_") if "/" in model_lower else ""
    if model_prefix in EMBEDDING_PROVIDERS:
        return model_prefix

    for provider_name, spec in EMBEDDING_PROVIDERS.items():
        if any(keyword in model_lower for keyword in spec.keywords):
            return provider_name

    if _is_local_base_url(api_base):
        if api_base and "11434" in api_base:
            return "ollama"
        return "vllm"

    for provider_name, spec in EMBEDDING_PROVIDERS.items():
        configured = provider_pool.get(provider_name)
        if not configured:
            continue
        if spec.is_local and configured.api_base:
            return provider_name
        if configured.api_key:
            return provider_name

    return "openai"


def _embedding_provider_env_key(provider: str, env: EnvStore) -> str:
    spec = EMBEDDING_PROVIDERS.get(provider)
    if not spec:
        return ""
    for key in spec.api_key_envs:
        value = env.get(key, "").strip()
        if value:
            return value
    return ""


def _iflytek_embedding_env(env: EnvStore) -> dict[str, str]:
    values: dict[str, str] = {}
    candidates = {
        "app_id": (
            "IFLYTEK_EMBEDDING_APPID",
            "IFLYTEK_EMBEDDING_APP_ID",
            "IFLYTEK_APPID",
            "IFLYTEK_OCR_APPID",
            "IFLYTEK_TTS_APPID",
            "XFYUN_EMBEDDING_APPID",
            "SPARK_EMBEDDING_APPID",
        ),
        "api_secret": (
            "IFLYTEK_API_SECRET",
            "IFLYTEK_EMBEDDING_API_SECRET",
            "IFLYTEK_SPARK_EMBEDDING_API_SECRET",
            "IFLYTEK_OCR_API_SECRET",
            "IFLYTEK_TTS_API_SECRET",
            "XFYUN_EMBEDDING_API_SECRET",
            "SPARK_EMBEDDING_API_SECRET",
        ),
        "domain": (
            "IFLYTEK_EMBEDDING_DOMAIN",
            "SPARK_EMBEDDING_DOMAIN",
        ),
    }
    for field_name, env_names in candidates.items():
        if field_name == "domain":
            values[field_name] = "para"
        for env_name in env_names:
            value = env.get(env_name, "").strip()
            if value:
                values[field_name] = value
                break
    return values


def resolve_embedding_runtime_config(
    catalog: dict[str, Any] | None = None,
    *,
    env_store: EnvStore | None = None,
    service: ModelCatalogService | None = None,
) -> ResolvedEmbeddingConfig:
    """Resolve active embedding config using provider-runtime normalization."""
    env = env_store or get_env_store()
    catalog_service = service or get_model_catalog_service()
    loaded = catalog if catalog is not None else catalog_service.load()
    profile = catalog_service.get_active_profile(loaded, "embedding")
    model = catalog_service.get_active_model(loaded, "embedding")
    summary = env.as_summary()
    env_values = env.load()
    explicit_env_keys = {key for key, value in env_values.items() if str(value).strip()}
    if env_store is None:
        for key in (
            "EMBEDDING_MODEL",
            "EMBEDDING_BINDING",
            "EMBEDDING_API_KEY",
            "EMBEDDING_HOST",
            "EMBEDDING_DIMENSION",
        ):
            if os.getenv(key, "").strip():
                explicit_env_keys.add(key)

    env_embedding_model = summary.embedding.get("model", "").strip()
    resolved_model = (
        env_embedding_model
        if "EMBEDDING_MODEL" in explicit_env_keys and env_embedding_model
        else _as_str((model or {}).get("model")) or env_embedding_model
    )
    if not resolved_model:
        raise ValueError("No active embedding model is configured. Please set it in Settings.")

    env_embedding_binding = _as_str(summary.embedding.get("binding", ""))
    binding_hint_raw = (
        env_embedding_binding
        if "EMBEDDING_BINDING" in explicit_env_keys and env_embedding_binding
        else _as_str((profile or {}).get("binding"))
    )
    binding_hint = _canonical_embedding_provider_name(binding_hint_raw)

    env_embedding_api_key = summary.embedding.get("api_key", "")
    env_embedding_host = summary.embedding.get("host", "")
    active_api_key = (
        env_embedding_api_key
        if "EMBEDDING_API_KEY" in explicit_env_keys and env_embedding_api_key
        else _as_str((profile or {}).get("api_key")) or env_embedding_api_key
    )
    active_api_base = (
        env_embedding_host
        if "EMBEDDING_HOST" in explicit_env_keys and env_embedding_host
        else _as_str((profile or {}).get("base_url")) or env_embedding_host
    )
    active_api_version = (
        _as_str((profile or {}).get("api_version")) or summary.embedding.get("api_version", "")
    )
    active_extra_headers = _to_headers((profile or {}).get("extra_headers"))
    env_embedding_dimension = summary.embedding.get("dimension")
    dimension = _resolve_embedding_dimension(
        env_embedding_dimension
        if "EMBEDDING_DIMENSION" in explicit_env_keys and env_embedding_dimension
        else (model or {}).get("dimension") or env_embedding_dimension or 3072
    )

    provider_pool = _collect_embedding_provider_pool(loaded)
    provider_name = _resolve_embedding_provider(
        hint=binding_hint,
        model=resolved_model,
        api_base=active_api_base or None,
        provider_pool=provider_pool,
    )
    spec = EMBEDDING_PROVIDERS[provider_name]
    mapped = provider_pool.get(provider_name)

    provider_credentials = loaded.get("provider_credentials") if isinstance(loaded.get("provider_credentials"), dict) else {}
    iflytek_credentials = provider_credentials.get("iflytek") if isinstance(provider_credentials.get("iflytek"), dict) else {}
    siliconflow_credentials = (
        provider_credentials.get("siliconflow")
        if isinstance(provider_credentials.get("siliconflow"), dict)
        else {}
    )

    api_key = active_api_key or (mapped.api_key if mapped else "")
    if not api_key:
        api_key = _embedding_provider_env_key(provider_name, env)

    api_base = active_api_base or ((mapped.api_base or "") if mapped else "")
    if not api_base and spec.default_api_base:
        api_base = spec.default_api_base
    if provider_name == "iflytek_spark":
        api_key = _as_str(iflytek_credentials.get("api_key")) or active_api_key or api_key
    elif "siliconflow" in (api_base or "").lower():
        api_key = _as_str(siliconflow_credentials.get("api_key")) or active_api_key or api_key
    api_version = active_api_version or ((mapped.api_version or "") if mapped else "")
    extra_headers = active_extra_headers or ((mapped.extra_headers or {}) if mapped else {})

    if provider_name == "iflytek_spark":
        credential_headers = {
            "app_id": _as_str(iflytek_credentials.get("app_id")),
            "api_secret": _as_str(iflytek_credentials.get("api_secret")),
        }
        credential_headers = {key: value for key, value in credential_headers.items() if value}
        extra_headers = {**_iflytek_embedding_env(env), **credential_headers, **extra_headers}

    if spec.is_local and not api_key:
        api_key = "sk-no-key-required"

    return ResolvedEmbeddingConfig(
        model=resolved_model,
        provider_name=provider_name,
        provider_mode=spec.mode,
        binding_hint=binding_hint,
        binding=provider_name,
        api_key=api_key,
        base_url=api_base or None,
        effective_url=api_base or None,
        api_version=api_version or None,
        extra_headers=extra_headers,
        dimension=dimension,
        request_timeout=60,
        batch_size=10,
        batch_delay=0.0,
    )


def _resolve_search_max_results(catalog: dict[str, Any], default: int = 5) -> int:
    service = get_model_catalog_service()
    profile = service.get_active_profile(catalog, "search") or {}
    raw = profile.get("max_results")
    if raw is not None:
        try:
            return max(1, min(int(raw), 10))
        except (TypeError, ValueError):
            pass
    try:
        settings = load_config_with_main("main.yaml")
    except Exception:
        return default
    tools = settings.get("tools", {}) if isinstance(settings, dict) else {}
    web_search = tools.get("web_search", {}) if isinstance(tools, dict) else {}
    raw = web_search.get("max_results") if isinstance(web_search, dict) else None
    if raw is None:
        web = tools.get("web", {}) if isinstance(tools, dict) else {}
        search = web.get("search", {}) if isinstance(web, dict) else {}
        raw = search.get("max_results") if isinstance(search, dict) else None
    if raw is None:
        return default
    try:
        return max(1, min(int(raw), 10))
    except (TypeError, ValueError):
        return default


def _provider_env_key(provider: str, env: EnvStore) -> str:
    for key in SEARCH_ENV_FALLBACK.get(provider, ()):
        value = env.get(key, "").strip()
        if value:
            return value
    return ""


def resolve_search_runtime_config(
    catalog: dict[str, Any] | None = None,
    *,
    env_store: EnvStore | None = None,
    service: ModelCatalogService | None = None,
) -> ResolvedSearchConfig:
    """Resolve active web-search config with env/catalog fallback."""
    env = env_store or get_env_store()
    catalog_service = service or get_model_catalog_service()
    loaded = catalog if catalog is not None else catalog_service.load()
    profile = catalog_service.get_active_profile(loaded, "search") or {}
    summary = env.as_summary().search

    requested_provider = (
        _as_str(profile.get("provider"))
        or _as_str(summary.get("provider"))
        or env.get("SEARCH_PROVIDER", "").strip()
        or "brave"
    ).lower()
    provider = requested_provider
    api_key = _as_str(profile.get("api_key")) or _as_str(summary.get("api_key"))
    base_url = _as_str(profile.get("base_url")) or _as_str(summary.get("base_url"))
    proxy = _as_str(profile.get("proxy")) or env.get("SEARCH_PROXY", "").strip() or None
    max_results = _resolve_search_max_results(loaded)

    deprecated = provider in DEPRECATED_SEARCH_PROVIDERS
    unsupported = provider not in SUPPORTED_SEARCH_PROVIDERS
    fallback_reason: str | None = None
    missing_credentials = False

    if provider == "searxng" and not base_url:
        base_url = env.get("SEARXNG_BASE_URL", "").strip()
    elif provider == "iflytek_spark" and not base_url:
        base_url = "https://search-api-open.cn-huabei-1.xf-yun.com/v2/search"

    if provider in SEARCH_ENV_FALLBACK and not api_key:
        api_key = _provider_env_key(provider, env)

    if provider in {"perplexity", "serper", "iflytek_spark"} and not api_key:
        missing_credentials = True

    if unsupported:
        return ResolvedSearchConfig(
            provider=provider,
            requested_provider=requested_provider,
            api_key=api_key,
            base_url=base_url,
            max_results=max_results,
            proxy=proxy,
            unsupported_provider=True,
            deprecated_provider=deprecated,
            missing_credentials=missing_credentials,
        )

    if provider in {"brave", "tavily", "jina"} and not api_key:
        fallback_reason = f"{provider} requires api_key, falling back to duckduckgo"
        provider = "duckduckgo"
    elif provider == "searxng" and not base_url:
        fallback_reason = "searxng requires base_url, falling back to duckduckgo"
        provider = "duckduckgo"

    return ResolvedSearchConfig(
        provider=provider,
        requested_provider=requested_provider,
        api_key=api_key,
        base_url=base_url,
        max_results=max_results,
        proxy=proxy,
        unsupported_provider=False,
        deprecated_provider=deprecated,
        missing_credentials=missing_credentials,
        fallback_reason=fallback_reason,
    )


def search_provider_state(provider: str | None) -> str:
    """Return provider status class for UI/CLI/system output."""
    value = (provider or "").strip().lower()
    if not value:
        return "not_configured"
    if value in DEPRECATED_SEARCH_PROVIDERS:
        return "deprecated"
    if value not in SUPPORTED_SEARCH_PROVIDERS:
        return "unsupported"
    return "supported"


def _is_openai_compatible_binding(binding: str | None) -> bool:
    canonical = canonical_provider_name(binding) or (binding or "").strip().lower()
    if canonical in {"custom", "azure_openai"}:
        return True
    spec = find_by_name(canonical)
    return bool(spec and not spec.is_oauth)


def _set_openai_env_vars(api_key: str | None, base_url: str | None, *, source: str) -> None:
    if api_key and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = api_key
        logger.debug("Set OPENAI_API_KEY env var (%s)", source)

    if base_url and not os.getenv("OPENAI_BASE_URL"):
        os.environ["OPENAI_BASE_URL"] = base_url.rstrip("/")
        logger.debug("Set OPENAI_BASE_URL env var to %s (%s)", base_url, source)


def initialize_environment() -> None:
    """Initialize OpenAI-compatible env vars for SDK helpers."""
    try:
        resolved = resolve_llm_runtime_config()
        binding = resolved.binding
        api_key = resolved.api_key
        base_url = resolved.effective_url
    except Exception:
        env_store = get_env_store()
        binding = _strip_value(env_store.get("LLM_BINDING")) or "openai"
        api_key = _strip_value(env_store.get("LLM_API_KEY"))
        base_url = _strip_value(env_store.get("LLM_HOST"))

    if _is_openai_compatible_binding(binding):
        _set_openai_env_vars(api_key, base_url, source="initialize_environment")


def _get_llm_config_from_env() -> LLMConfig:
    env_store = get_env_store()
    binding = _strip_value(env_store.get("LLM_BINDING")) or "openai"
    model = _strip_value(env_store.get("LLM_MODEL"))
    if not model:
        raise LLMConfigError("No active LLM model is configured.")
    api_key = _strip_value(env_store.get("LLM_API_KEY")) or ""
    base_url = _strip_value(env_store.get("LLM_HOST")) or None
    api_version = _strip_value(env_store.get("LLM_API_VERSION"))
    spec = find_by_name(canonical_provider_name(binding) or binding) or find_by_name("openai") or PROVIDERS[0]
    if spec.name == "iflytek_spark_ws":
        if not api_key:
            api_key = _llm_provider_env_key(spec, env_store)
        base_url = _iflytek_ws_default_base(model, base_url, binding)
        model = IFLYTEK_SPARK_MODEL
    if not api_key and not spec.is_local and not spec.is_oauth:
        api_key = _llm_provider_env_key(spec, env_store)
    if not base_url:
        base_url = spec.default_api_base or None
    if spec.is_local and not api_key:
        api_key = "sk-no-key-required"
    return LLMConfig(
        binding=spec.name,
        provider_name=spec.name,
        provider_mode=spec.mode,
        model=model,
        api_key=api_key,
        base_url=base_url,
        effective_url=base_url,
        api_version=api_version,
    )


def _get_llm_config_from_resolver() -> LLMConfig:
    resolved = resolve_llm_runtime_config()
    if not resolved.model:
        raise LLMConfigError("No active LLM model is configured.")
    if not resolved.effective_url and resolved.provider_mode != "oauth":
        raise LLMConfigError("No effective LLM endpoint resolved.")
    return LLMConfig(
        model=resolved.model,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        effective_url=resolved.effective_url,
        binding=resolved.binding,
        provider_name=resolved.provider_name,
        provider_mode=resolved.provider_mode,
        api_version=resolved.api_version,
        extra_headers=resolved.extra_headers,
        reasoning_effort=resolved.reasoning_effort,
    )


_LLM_CONFIG_CACHE: LLMConfig | None = None


def get_llm_config() -> LLMConfig:
    """Load and cache the active NG LLM configuration."""
    global _LLM_CONFIG_CACHE

    if _LLM_CONFIG_CACHE is not None:
        return _LLM_CONFIG_CACHE

    try:
        _LLM_CONFIG_CACHE = _get_llm_config_from_resolver()
    except Exception as exc:
        logger.warning(
            "NG LLM runtime resolver failed, falling back to env path: %s",
            exc,
        )
        _LLM_CONFIG_CACHE = _get_llm_config_from_env()
    return _LLM_CONFIG_CACHE


async def get_llm_config_async() -> LLMConfig:
    """Async wrapper for API symmetry with legacy call sites."""
    return get_llm_config()


def clear_llm_config_cache() -> None:
    """Clear cached LLM configuration."""
    global _LLM_CONFIG_CACHE

    _LLM_CONFIG_CACHE = None


def reload_config() -> LLMConfig:
    """Reload and return the LLM configuration."""
    clear_llm_config_cache()
    return get_llm_config()


def uses_max_completion_tokens(model: str) -> bool:
    """Return whether the model expects ``max_completion_tokens``."""
    model_lower = model.lower()
    patterns = [
        r"^o\d",
        r"^gpt-4o",
        r"^gpt-[5-9]",
        r"^gpt-\d{2,}",
    ]

    for pattern in patterns:
        if re.match(pattern, model_lower):
            return True

    return False


def get_token_limit_kwargs(model: str, max_tokens: int) -> dict[str, int]:
    """Return the token-limit keyword expected by the model."""
    if uses_max_completion_tokens(model):
        return {"max_completion_tokens": max_tokens}
    return {"max_tokens": max_tokens}


__all__ = [
    "ConfigSummary",
    "DEPRECATED_SEARCH_PROVIDERS",
    "EMBEDDING_PROVIDERS",
    "EMBEDDING_PROVIDER_ALIASES",
    "EmbeddingProviderSpec",
    "ENV_KEY_ORDER",
    "ENV_PATH",
    "LLMConfig",
    "LLMConfigError",
    "ModelCatalogService",
    "NANOBOT_LLM_PROVIDERS",
    "PROVIDERS",
    "ProviderSpec",
    "ResolvedEmbeddingConfig",
    "ResolvedLLMConfig",
    "ResolvedSearchConfig",
    "SUPPORTED_SEARCH_PROVIDERS",
    "canonical_provider_name",
    "clear_llm_config_cache",
    "find_by_model",
    "find_by_name",
    "find_gateway",
    "get_env_store",
    "get_agent_params",
    "get_config_test_runner",
    "get_kb_config_service",
    "get_llm_config",
    "get_llm_config_async",
    "get_model_catalog_service",
    "get_path_from_config",
    "get_token_limit_kwargs",
    "initialize_environment",
    "load_config_with_main",
    "load_config_with_main_async",
    "parse_language",
    "reload_config",
    "resolve_embedding_runtime_config",
    "resolve_llm_runtime_config",
    "resolve_search_runtime_config",
    "search_provider_state",
    "strip_provider_prefix",
    "uses_max_completion_tokens",
]

