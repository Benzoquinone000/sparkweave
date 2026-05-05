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
        default_model="openai/gpt-5.2",
        model_options=(
            "openai/gpt-5.2",
            "anthropic/claude-opus-4-1-20250805",
            "anthropic/claude-sonnet-4-20250514",
            "google/gemini-3-pro-preview",
            "deepseek/deepseek-reasoner",
        ),
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
        default_model="gpt-5.2",
        model_options=("gpt-5.2", "gpt-5-mini", "claude-opus-4-1-20250805", "gemini-3-pro-preview"),
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
        model_options=("deepseek-ai/DeepSeek-R1", "deepseek-ai/DeepSeek-V3", "Qwen/Qwen3-235B-A22B"),
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
        default_model="claude-opus-4-1-20250805",
        model_options=(
            "claude-opus-4-1-20250805",
            "claude-opus-4-20250514",
            "claude-sonnet-4-20250514",
            "claude-3-5-haiku-20241022",
        ),
    ),
    ProviderSpec(
        "openai",
        ("openai", "gpt"),
        "OPENAI_API_KEY",
        display_name="OpenAI",
        default_api_base="https://api.openai.com/v1",
        supports_max_completion_tokens=True,
        default_model="gpt-5.2",
        model_options=("gpt-5.2", "gpt-5.2-pro", "gpt-5-mini", "gpt-5-nano", "gpt-4.1", "gpt-4.1-mini"),
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
        default_model="deepseek-chat",
        model_options=("deepseek-chat", "deepseek-reasoner"),
    ),
    ProviderSpec(
        "gemini",
        ("gemini",),
        "GEMINI_API_KEY",
        display_name="Gemini",
        default_api_base="https://generativelanguage.googleapis.com/v1beta/openai/",
        default_model="gemini-3-pro-preview",
        model_options=(
            "gemini-3-pro-preview",
            "gemini-3-flash-preview",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.0-flash-lite",
        ),
    ),
    ProviderSpec(
        "zhipu",
        ("zhipu", "glm", "zai"),
        "ZAI_API_KEY",
        display_name="Zhipu AI",
        env_extras=(("ZHIPUAI_API_KEY", "{api_key}"),),
        default_api_base="https://open.bigmodel.cn/api/paas/v4",
        default_model="glm-4.5",
        model_options=("glm-4.5", "glm-4.5-air", "glm-4-plus", "glm-4-air"),
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
            "qwen3.5-plus",
            "qwen3.5-flash",
            "qwen3-coder-plus",
        ),
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
    ),
    ProviderSpec(
        "moonshot",
        ("moonshot", "kimi"),
        "MOONSHOT_API_KEY",
        display_name="Moonshot",
        default_api_base="https://api.moonshot.ai/v1",
        default_model="kimi-k2.5",
        model_options=("kimi-k2.5", "kimi-k2-turbo-preview", "moonshot-v1-128k", "moonshot-v1-32k"),
        model_overrides=(("kimi-k2.5", {"temperature": 1.0}),),
    ),
    ProviderSpec(
        "minimax",
        ("minimax",),
        "MINIMAX_API_KEY",
        display_name="MiniMax",
        default_api_base="https://api.minimax.io/v1",
        default_model="MiniMax-M2.7",
        model_options=("MiniMax-M2.7", "MiniMax-M2.7-highspeed", "MiniMax-M2.5", "MiniMax-M2"),
    ),
    ProviderSpec(
        "mistral",
        ("mistral",),
        "MISTRAL_API_KEY",
        display_name="Mistral",
        default_api_base="https://api.mistral.ai/v1",
        default_model="mistral-large-2512",
        model_options=("mistral-large-2512", "mistral-medium-2508", "mistral-small-2603", "magistral-medium-2509"),
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


EMBEDDING_PROVIDERS: dict[str, EmbeddingProviderSpec] = {
    "openai": EmbeddingProviderSpec(
        label="OpenAI",
        default_api_base="https://api.openai.com/v1",
        keywords=("openai", "text-embedding", "ada-002", "embedding-3"),
        is_local=False,
        api_key_envs=("OPENAI_API_KEY",),
        default_model="text-embedding-3-large",
        default_dim=3072,
    ),
    "azure_openai": EmbeddingProviderSpec(
        label="Azure OpenAI",
        mode="direct",
        default_api_base="",
        keywords=("azure", "aoai"),
        is_local=False,
        api_key_envs=("AZURE_OPENAI_API_KEY", "AZURE_API_KEY"),
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
    ),
    "iflytek_spark": EmbeddingProviderSpec(
        label="iFlytek Spark Embedding",
        adapter="iflytek_spark",
        default_api_base="https://emb-cn-huabei-1.xf-yun.com/",
        keywords=("iflytek", "xfyun", "xunfei", "llm-embedding"),
        is_local=False,
        api_key_envs=(
            "IFLYTEK_EMBEDDING_API_KEY",
            "IFLYTEK_SPARK_EMBEDDING_API_KEY",
            "XFYUN_EMBEDDING_API_KEY",
            "SPARK_EMBEDDING_API_KEY",
        ),
        default_model="llm-embedding",
        default_dim=2560,
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
    ),
    "vllm": EmbeddingProviderSpec(
        label="vLLM / LM Studio",
        mode="local",
        default_api_base="http://localhost:8000/v1",
        keywords=("vllm", "lmstudio"),
        is_local=True,
        api_key_envs=("HOSTED_VLLM_API_KEY",),
    ),
    "custom": EmbeddingProviderSpec(
        label="OpenAI Compatible",
        mode="direct",
        default_api_base="",
        keywords=(),
        is_local=False,
        api_key_envs=("OPENAI_API_KEY",),
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
DEFAULT_IFLYTEK_TTS_URL = "wss://cbm01.cn-huabei-1.xf-yun.com/v1/private/mcd9m97e6"
DEFAULT_IFLYTEK_TTS_VOICE = "x5_lingxiaoxuan_flow"


ENV_KEY_ORDER = (
    "BACKEND_PORT",
    "FRONTEND_PORT",
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


class EnvStore:
    """Small `.env` reader compatible with the existing SparkWeave layout."""

    def __init__(self, path: Path = ENV_PATH):
        self.path = path

    def load(self) -> OrderedDict[str, str]:
        if self.path.exists():
            values = _parse_env_lines(self.path.read_text(encoding="utf-8").splitlines())
        else:
            values = OrderedDict()
        for key, value in values.items():
            os.environ.setdefault(key, value)
        return values

    def get(self, key: str, default: str = "") -> str:
        values = self.load()
        return values.get(key, os.getenv(key, default))

    def as_summary(self) -> ConfigSummary:
        values = self.load()
        return ConfigSummary(
            backend_port=_safe_int(values.get("BACKEND_PORT") or os.getenv("BACKEND_PORT"), 8001),
            frontend_port=_safe_int(
                values.get("FRONTEND_PORT") or os.getenv("FRONTEND_PORT"), 3782
            ),
            llm={
                "binding": values.get("LLM_BINDING", os.getenv("LLM_BINDING", "openai")),
                "model": values.get("LLM_MODEL", os.getenv("LLM_MODEL", "")),
                "api_key": values.get("LLM_API_KEY", os.getenv("LLM_API_KEY", "")),
                "host": values.get("LLM_HOST", os.getenv("LLM_HOST", "")),
                "api_version": values.get(
                    "LLM_API_VERSION", os.getenv("LLM_API_VERSION", "")
                ),
            },
            embedding={
                "binding": values.get(
                    "EMBEDDING_BINDING", os.getenv("EMBEDDING_BINDING", "openai")
                ),
                "model": values.get("EMBEDDING_MODEL", os.getenv("EMBEDDING_MODEL", "")),
                "api_key": values.get(
                    "EMBEDDING_API_KEY", os.getenv("EMBEDDING_API_KEY", "")
                ),
                "host": values.get("EMBEDDING_HOST", os.getenv("EMBEDDING_HOST", "")),
                "dimension": values.get(
                    "EMBEDDING_DIMENSION", os.getenv("EMBEDDING_DIMENSION", "3072")
                ),
                "api_version": values.get(
                    "EMBEDDING_API_VERSION", os.getenv("EMBEDDING_API_VERSION", "")
                ),
            },
            search={
                "provider": values.get("SEARCH_PROVIDER", os.getenv("SEARCH_PROVIDER", "")),
                "api_key": values.get("SEARCH_API_KEY", os.getenv("SEARCH_API_KEY", "")),
                "base_url": values.get("SEARCH_BASE_URL", os.getenv("SEARCH_BASE_URL", "")),
                "proxy": values.get("SEARCH_PROXY", os.getenv("SEARCH_PROXY", "")),
            },
            ocr={
                "provider": values.get(
                    "SPARKWEAVE_OCR_PROVIDER",
                    os.getenv("SPARKWEAVE_OCR_PROVIDER", "iflytek"),
                ),
                "strategy": values.get(
                    "SPARKWEAVE_PDF_OCR_STRATEGY",
                    os.getenv("SPARKWEAVE_PDF_OCR_STRATEGY", "auto"),
                ),
                "timeout": values.get(
                    "SPARKWEAVE_OCR_TIMEOUT",
                    os.getenv("SPARKWEAVE_OCR_TIMEOUT", "30"),
                ),
                "max_pages": values.get(
                    "SPARKWEAVE_OCR_MAX_PAGES",
                    os.getenv("SPARKWEAVE_OCR_MAX_PAGES", "20"),
                ),
                "dpi": values.get("SPARKWEAVE_OCR_DPI", os.getenv("SPARKWEAVE_OCR_DPI", "180")),
                "min_text_chars": values.get(
                    "SPARKWEAVE_OCR_MIN_TEXT_CHARS",
                    os.getenv("SPARKWEAVE_OCR_MIN_TEXT_CHARS", "80"),
                ),
                "app_id": values.get("IFLYTEK_OCR_APPID", os.getenv("IFLYTEK_OCR_APPID", "")),
                "api_key": values.get("IFLYTEK_OCR_API_KEY", os.getenv("IFLYTEK_OCR_API_KEY", "")),
                "api_secret": values.get(
                    "IFLYTEK_OCR_API_SECRET",
                    os.getenv("IFLYTEK_OCR_API_SECRET", ""),
                ),
                "url": values.get(
                    "IFLYTEK_OCR_URL",
                    os.getenv("IFLYTEK_OCR_URL", DEFAULT_IFLYTEK_OCR_URL),
                ),
                "service_id": values.get(
                    "IFLYTEK_OCR_SERVICE_ID",
                    os.getenv("IFLYTEK_OCR_SERVICE_ID", DEFAULT_IFLYTEK_OCR_SERVICE_ID),
                ),
                "category": values.get(
                    "IFLYTEK_OCR_CATEGORY",
                    os.getenv("IFLYTEK_OCR_CATEGORY", DEFAULT_IFLYTEK_OCR_CATEGORY),
                ),
            },
            tts={
                "provider": values.get(
                    "SPARKWEAVE_TTS_PROVIDER",
                    os.getenv("SPARKWEAVE_TTS_PROVIDER", "iflytek"),
                ),
                "timeout": values.get(
                    "SPARKWEAVE_TTS_TIMEOUT",
                    os.getenv("SPARKWEAVE_TTS_TIMEOUT", "30"),
                ),
                "app_id": values.get("IFLYTEK_TTS_APPID", os.getenv("IFLYTEK_TTS_APPID", "")),
                "api_key": values.get("IFLYTEK_TTS_API_KEY", os.getenv("IFLYTEK_TTS_API_KEY", "")),
                "api_secret": values.get(
                    "IFLYTEK_TTS_API_SECRET",
                    os.getenv("IFLYTEK_TTS_API_SECRET", ""),
                ),
                "url": values.get(
                    "IFLYTEK_TTS_URL",
                    os.getenv("IFLYTEK_TTS_URL", DEFAULT_IFLYTEK_TTS_URL),
                ),
                "voice": values.get(
                    "IFLYTEK_TTS_VOICE",
                    os.getenv("IFLYTEK_TTS_VOICE", DEFAULT_IFLYTEK_TTS_VOICE),
                ),
                "encoding": values.get(
                    "IFLYTEK_TTS_ENCODING",
                    os.getenv("IFLYTEK_TTS_ENCODING", "lame"),
                ),
                "sample_rate": values.get(
                    "IFLYTEK_TTS_SAMPLE_RATE",
                    os.getenv("IFLYTEK_TTS_SAMPLE_RATE", "24000"),
                ),
                "channels": values.get(
                    "IFLYTEK_TTS_CHANNELS",
                    os.getenv("IFLYTEK_TTS_CHANNELS", "1"),
                ),
                "bit_depth": values.get(
                    "IFLYTEK_TTS_BIT_DEPTH",
                    os.getenv("IFLYTEK_TTS_BIT_DEPTH", "16"),
                ),
                "frame_size": values.get(
                    "IFLYTEK_TTS_FRAME_SIZE",
                    os.getenv("IFLYTEK_TTS_FRAME_SIZE", "0"),
                ),
                "speed": values.get(
                    "IFLYTEK_TTS_SPEED",
                    os.getenv("IFLYTEK_TTS_SPEED", "50"),
                ),
                "volume": values.get(
                    "IFLYTEK_TTS_VOLUME",
                    os.getenv("IFLYTEK_TTS_VOLUME", "50"),
                ),
                "pitch": values.get(
                    "IFLYTEK_TTS_PITCH",
                    os.getenv("IFLYTEK_TTS_PITCH", "50"),
                ),
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
        tts_service = services.get("tts", {})

        llm_profile = self._get_active_profile(llm_service)
        llm_model = self._get_active_model(llm_service, llm_profile)
        embedding_profile = self._get_active_profile(embedding_service)
        embedding_model = self._get_active_model(embedding_service, embedding_profile)
        search_profile = self._get_active_profile(search_service)
        ocr_profile = self._get_active_profile(ocr_service)
        ocr_extra = (ocr_profile or {}).get("extra_headers") or {}
        tts_profile = self._get_active_profile(tts_service)
        tts_extra = (tts_profile or {}).get("extra_headers") or {}

        current = self.load()
        return {
            "BACKEND_PORT": current.get("BACKEND_PORT", os.getenv("BACKEND_PORT", "8001")),
            "FRONTEND_PORT": current.get("FRONTEND_PORT", os.getenv("FRONTEND_PORT", "3782")),
            "LLM_BINDING": str((llm_profile or {}).get("binding") or "openai"),
            "LLM_MODEL": str((llm_model or {}).get("model") or ""),
            "LLM_API_KEY": str((llm_profile or {}).get("api_key") or ""),
            "LLM_HOST": str((llm_profile or {}).get("base_url") or ""),
            "LLM_API_VERSION": str((llm_profile or {}).get("api_version") or ""),
            "EMBEDDING_BINDING": str((embedding_profile or {}).get("binding") or "openai"),
            "EMBEDDING_MODEL": str((embedding_model or {}).get("model") or ""),
            "EMBEDDING_API_KEY": str((embedding_profile or {}).get("api_key") or ""),
            "EMBEDDING_HOST": str((embedding_profile or {}).get("base_url") or ""),
            "EMBEDDING_DIMENSION": str((embedding_model or {}).get("dimension") or 3072),
            "EMBEDDING_API_VERSION": str((embedding_profile or {}).get("api_version") or ""),
            "SEARCH_PROVIDER": str((search_profile or {}).get("provider") or ""),
            "SEARCH_API_KEY": str((search_profile or {}).get("api_key") or ""),
            "SEARCH_BASE_URL": str((search_profile or {}).get("base_url") or ""),
            "SEARCH_PROXY": str((search_profile or {}).get("proxy") or ""),
            "SPARKWEAVE_OCR_PROVIDER": str(
                (ocr_profile or {}).get("provider")
                or current.get("SPARKWEAVE_OCR_PROVIDER", "iflytek")
            ),
            "SPARKWEAVE_PDF_OCR_STRATEGY": str(
                (ocr_profile or {}).get("strategy")
                or current.get("SPARKWEAVE_PDF_OCR_STRATEGY", "auto")
            ),
            "SPARKWEAVE_OCR_TIMEOUT": str(
                (ocr_profile or {}).get("timeout") or current.get("SPARKWEAVE_OCR_TIMEOUT", "30")
            ),
            "SPARKWEAVE_OCR_MAX_PAGES": str(
                (ocr_profile or {}).get("max_pages")
                or current.get("SPARKWEAVE_OCR_MAX_PAGES", "20")
            ),
            "SPARKWEAVE_OCR_DPI": str(
                (ocr_profile or {}).get("dpi") or current.get("SPARKWEAVE_OCR_DPI", "180")
            ),
            "SPARKWEAVE_OCR_MIN_TEXT_CHARS": str(
                (ocr_profile or {}).get("min_text_chars")
                or current.get("SPARKWEAVE_OCR_MIN_TEXT_CHARS", "80")
            ),
            "IFLYTEK_OCR_APPID": str(ocr_extra.get("app_id") or current.get("IFLYTEK_OCR_APPID", "")),
            "IFLYTEK_OCR_API_KEY": str(
                (ocr_profile or {}).get("api_key") or current.get("IFLYTEK_OCR_API_KEY", "")
            ),
            "IFLYTEK_OCR_API_SECRET": str(
                ocr_extra.get("api_secret") or current.get("IFLYTEK_OCR_API_SECRET", "")
            ),
            "IFLYTEK_OCR_URL": str(
                (ocr_profile or {}).get("base_url")
                or current.get("IFLYTEK_OCR_URL", DEFAULT_IFLYTEK_OCR_URL)
            ),
            "IFLYTEK_OCR_SERVICE_ID": str(
                ocr_extra.get("service_id")
                or current.get("IFLYTEK_OCR_SERVICE_ID", DEFAULT_IFLYTEK_OCR_SERVICE_ID)
            ),
            "IFLYTEK_OCR_CATEGORY": str(
                ocr_extra.get("category")
                or current.get("IFLYTEK_OCR_CATEGORY", DEFAULT_IFLYTEK_OCR_CATEGORY)
            ),
            "SPARKWEAVE_TTS_PROVIDER": str(
                (tts_profile or {}).get("provider")
                or current.get("SPARKWEAVE_TTS_PROVIDER", "iflytek")
            ),
            "SPARKWEAVE_TTS_TIMEOUT": str(
                (tts_profile or {}).get("timeout") or current.get("SPARKWEAVE_TTS_TIMEOUT", "30")
            ),
            "IFLYTEK_TTS_APPID": str(tts_extra.get("app_id") or current.get("IFLYTEK_TTS_APPID", "")),
            "IFLYTEK_TTS_API_KEY": str(
                (tts_profile or {}).get("api_key") or current.get("IFLYTEK_TTS_API_KEY", "")
            ),
            "IFLYTEK_TTS_API_SECRET": str(
                tts_extra.get("api_secret") or current.get("IFLYTEK_TTS_API_SECRET", "")
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


def _tts_shell() -> dict[str, Any]:
    return {"active_profile_id": None, "profiles": []}


def _default_catalog() -> dict[str, Any]:
    return {
        "version": 1,
        "services": {
            "llm": _service_shell(),
            "embedding": _service_shell(),
            "search": _search_shell(),
            "ocr": _ocr_shell(),
            "tts": _tts_shell(),
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
        if self.path.exists():
            loaded = json.loads(self.path.read_text(encoding="utf-8") or "{}")
            catalog.update({k: v for k, v in loaded.items() if k != "services"})
            catalog["services"].update(loaded.get("services", {}))
        hydrated = self._hydrate_missing_services_from_env(catalog)
        synced = self._sync_active_services_from_env(catalog)
        self._normalize(catalog)
        if hydrated or synced or not self.path.exists():
            self.save(catalog)
        return catalog

    def save(self, catalog: dict[str, Any]) -> dict[str, Any]:
        """Normalize and persist the model catalog."""
        normalized = deepcopy(catalog)
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
        if not ocr_service.get("profiles") and (
            summary.ocr["provider"]
            or summary.ocr["app_id"]
            or summary.ocr["api_key"]
            or summary.ocr["api_secret"]
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
                        "base_url": summary.ocr["url"],
                        "api_key": summary.ocr["api_key"],
                        "timeout": summary.ocr["timeout"] or "30",
                        "max_pages": summary.ocr["max_pages"] or "20",
                        "dpi": summary.ocr["dpi"] or "180",
                        "min_text_chars": summary.ocr["min_text_chars"] or "80",
                        "extra_headers": {
                            "app_id": summary.ocr["app_id"],
                            "api_secret": summary.ocr["api_secret"],
                            "service_id": summary.ocr["service_id"] or DEFAULT_IFLYTEK_OCR_SERVICE_ID,
                            "category": summary.ocr["category"] or DEFAULT_IFLYTEK_OCR_CATEGORY,
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

        return changed

    def _sync_active_services_from_env(self, catalog: dict[str, Any]) -> bool:
        """Sync active catalog values from explicitly present `.env` keys."""
        env_values = get_env_store().load()
        if not env_values:
            return False

        summary = get_env_store().as_summary()
        services = catalog.setdefault("services", {})
        changed = False

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
                    "timeout": "30",
                    "max_pages": "20",
                    "dpi": "180",
                    "min_text_chars": "80",
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

        if {"LLM_BINDING", "LLM_MODEL", "LLM_API_KEY", "LLM_HOST", "LLM_API_VERSION"}.intersection(
            env_values
        ):
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
        }.intersection(env_values):
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
        ):
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
        }
        if ocr_keys.intersection(env_values):
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
            ):
                if env_key in env_values and profile.get(field_name) != value:
                    profile[field_name] = value
                    changed = True
            for env_key, field_name, value in (
                ("IFLYTEK_OCR_APPID", "app_id", summary.ocr["app_id"]),
                ("IFLYTEK_OCR_API_SECRET", "api_secret", summary.ocr["api_secret"]),
                ("IFLYTEK_OCR_SERVICE_ID", "service_id", summary.ocr["service_id"]),
                ("IFLYTEK_OCR_CATEGORY", "category", summary.ocr["category"]),
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
        if tts_keys.intersection(env_values):
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
        services.setdefault("tts", _tts_shell())
        for service_name in ("llm", "embedding", "search", "ocr", "tts"):
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
                    profile.setdefault("base_url", DEFAULT_IFLYTEK_OCR_URL)
                    profile.setdefault("timeout", "30")
                    profile.setdefault("max_pages", "20")
                    profile.setdefault("dpi", "180")
                    profile.setdefault("min_text_chars", "80")
                    extra_headers = profile.setdefault("extra_headers", {})
                    extra_headers.setdefault("app_id", "")
                    extra_headers.setdefault("api_secret", "")
                    extra_headers.setdefault("service_id", DEFAULT_IFLYTEK_OCR_SERVICE_ID)
                    extra_headers.setdefault("category", DEFAULT_IFLYTEK_OCR_CATEGORY)
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
                "IFLYTEK_SPARK_API_PASSWORD",
                "IFLYTEK_SPARK_API_KEY",
                "XFYUN_SPARK_API_PASSWORD",
                "XFYUN_SPARK_API_KEY",
                "IFLYTEK_SPARK_WS_API_KEY",
                "IFLYTEK_WS_API_KEY",
                "XFYUN_WS_API_KEY",
                "SPARK_WS_API_KEY",
            ]
        )
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
    for field, env_names in candidates.items():
        for env_name in env_names:
            value = env.get(env_name, "").strip()
            if value:
                values[field] = value
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
        resolved_model = "gpt-4o-mini"

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
            "XFYUN_EMBEDDING_APPID",
            "SPARK_EMBEDDING_APPID",
        ),
        "api_secret": (
            "IFLYTEK_EMBEDDING_API_SECRET",
            "IFLYTEK_SPARK_EMBEDDING_API_SECRET",
            "XFYUN_EMBEDDING_API_SECRET",
            "SPARK_EMBEDDING_API_SECRET",
        ),
        "domain": (
            "IFLYTEK_EMBEDDING_DOMAIN",
            "SPARK_EMBEDDING_DOMAIN",
        ),
    }
    for field, env_names in candidates.items():
        if field == "domain":
            values[field] = "para"
        for env_name in env_names:
            value = env.get(env_name, "").strip()
            if value:
                values[field] = value
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

    resolved_model = (
        _as_str((model or {}).get("model")) or summary.embedding.get("model", "").strip()
    )
    if not resolved_model:
        raise ValueError("No active embedding model is configured. Please set it in Settings.")

    binding_hint_raw = _as_str((profile or {}).get("binding"))
    if not binding_hint_raw and "EMBEDDING_BINDING" in env_values:
        binding_hint_raw = _as_str(summary.embedding.get("binding", ""))
    binding_hint = _canonical_embedding_provider_name(binding_hint_raw)

    active_api_key = _as_str((profile or {}).get("api_key")) or summary.embedding.get("api_key", "")
    active_api_base = _as_str((profile or {}).get("base_url")) or summary.embedding.get("host", "")
    active_api_version = (
        _as_str((profile or {}).get("api_version")) or summary.embedding.get("api_version", "")
    )
    active_extra_headers = _to_headers((profile or {}).get("extra_headers"))
    dimension = _resolve_embedding_dimension(
        (model or {}).get("dimension") or summary.embedding.get("dimension") or 3072
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

    api_key = active_api_key or (mapped.api_key if mapped else "")
    if not api_key:
        api_key = _embedding_provider_env_key(provider_name, env)

    api_base = active_api_base or ((mapped.api_base or "") if mapped else "")
    if not api_base and spec.default_api_base:
        api_base = spec.default_api_base
    api_version = active_api_version or ((mapped.api_version or "") if mapped else "")
    extra_headers = active_extra_headers or ((mapped.extra_headers or {}) if mapped else {})

    if provider_name == "iflytek_spark":
        extra_headers = {**_iflytek_embedding_env(env), **extra_headers}

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

