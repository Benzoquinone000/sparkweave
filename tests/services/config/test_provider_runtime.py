"""Tests for SparkBot-style runtime config adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from sparkweave.services.config import (
    EnvStore,
    ModelCatalogService,
    resolve_llm_runtime_config,
    resolve_search_runtime_config,
)


def _build_catalog(
    *,
    llm_profile: dict | None = None,
    llm_model: dict | None = None,
    search_profile: dict | None = None,
) -> dict:
    llm_profile = llm_profile or {
        "id": "llm-p",
        "name": "LLM",
        "binding": "openai",
        "base_url": "",
        "api_key": "",
        "api_version": "",
        "extra_headers": {},
        "models": [{"id": "llm-m", "name": "m", "model": "gpt-4o-mini"}],
    }
    llm_model = llm_model or llm_profile["models"][0]
    search_profile = search_profile or {
        "id": "search-p",
        "name": "Search",
        "provider": "brave",
        "base_url": "",
        "api_key": "",
        "proxy": "",
        "models": [],
    }
    return {
        "version": 1,
        "services": {
            "llm": {
                "active_profile_id": llm_profile["id"],
                "active_model_id": llm_model["id"],
                "profiles": [llm_profile],
            },
            "embedding": {
                "active_profile_id": None,
                "active_model_id": None,
                "profiles": [],
            },
            "search": {
                "active_profile_id": search_profile["id"],
                "profiles": [search_profile],
            },
        },
    }


def _empty_env(tmp_path: Path) -> EnvStore:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "LLM_BINDING=",
                "LLM_MODEL=",
                "LLM_API_KEY=",
                "LLM_HOST=",
                "LLM_API_VERSION=",
                "IFLYTEK_APPID=",
                "IFLYTEK_API_KEY=",
                "IFLYTEK_API_SECRET=",
                "IFLYTEK_API_PASSWORD=",
                "IFLYTEK_MAAS_API_PASSWORD=",
                "SILICONFLOW_API_KEY=",
                "SEARCH_PROVIDER=",
                "SEARCH_API_KEY=",
                "SEARCH_BASE_URL=",
                "SEARCH_PROXY=",
                "BRAVE_API_KEY=",
                "TAVILY_API_KEY=",
                "JINA_API_KEY=",
                "SEARXNG_BASE_URL=",
                "PERPLEXITY_API_KEY=",
                "SERPER_API_KEY=",
                "IFLYTEK_SPARK_WS_APPID=",
                "IFLYTEK_SPARK_API_KEY=",
                "IFLYTEK_SPARK_API_PASSWORD=",
                "IFLYTEK_SPARK_WS_API_KEY=",
                "IFLYTEK_SPARK_WS_API_SECRET=",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return EnvStore(path=env_path)


def test_llm_explicit_binding_and_headers(tmp_path: Path) -> None:
    catalog = _build_catalog(
        llm_profile={
            "id": "llm-p",
            "name": "LLM",
            "binding": "dashscope",
            "base_url": "",
            "api_key": "dash-key",
            "api_version": "",
            "extra_headers": {"APP-Code": "abc"},
            "models": [{"id": "llm-m", "name": "q", "model": "qwen-max"}],
        }
    )
    resolved = resolve_llm_runtime_config(catalog=catalog, env_store=_empty_env(tmp_path))
    assert resolved.provider_name == "dashscope"
    assert resolved.provider_mode == "standard"
    assert resolved.effective_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert resolved.extra_headers == {"APP-Code": "abc"}


def test_llm_iflytek_spark_uses_openai_compatible_x2_default(tmp_path: Path) -> None:
    env = _empty_env(tmp_path)
    with env.path.open("a", encoding="utf-8") as handle:
        handle.write("IFLYTEK_SPARK_WS_APPID=appid-from-env\n")
        handle.write("IFLYTEK_SPARK_WS_API_KEY=ws-key-from-env\n")
        handle.write("IFLYTEK_SPARK_WS_API_SECRET=secret-from-env\n")

    catalog = _build_catalog(
        llm_profile={
            "id": "llm-p",
            "name": "LLM",
            "binding": "iflytek_spark_ws",
            "base_url": "",
            "api_key": "",
            "api_version": "",
            "extra_headers": {},
            "models": [{"id": "llm-m", "name": "4.0Ultra", "model": "4.0Ultra"}],
        }
    )
    resolved = resolve_llm_runtime_config(catalog=catalog, env_store=env)
    assert resolved.provider_name == "iflytek_spark_ws"
    assert resolved.provider_mode == "direct"
    assert resolved.model == "spark-x"
    assert resolved.effective_url == "https://spark-api-open.xf-yun.com/x2/"
    assert resolved.api_key == "ws-key-from-env"
    assert resolved.extra_headers == {}


def test_llm_iflytek_spark_replaces_legacy_ws_url(tmp_path: Path) -> None:
    catalog = _build_catalog(
        llm_profile={
            "id": "llm-p",
            "name": "LLM",
            "binding": "iflytek_spark_ws",
            "base_url": "wss://spark-api.xf-yun.com/v4.0/chat",
            "api_key": "ws-key",
            "api_version": "",
            "extra_headers": {"app_id": "appid", "api_secret": "secret"},
            "models": [{"id": "llm-m", "name": "generalv3.5", "model": "generalv3.5"}],
        }
    )
    resolved = resolve_llm_runtime_config(catalog=catalog, env_store=_empty_env(tmp_path))
    assert resolved.provider_name == "iflytek_spark_ws"
    assert resolved.model == "spark-x"
    assert resolved.effective_url == "https://spark-api-open.xf-yun.com/x2/"


def test_llm_legacy_iflytek_bindings_map_to_http_x2(tmp_path: Path) -> None:
    catalog = _build_catalog(
        llm_profile={
            "id": "llm-p",
            "name": "LLM",
            "binding": "iflytek_spark_x2",
            "base_url": "",
            "api_key": "ws-key",
            "api_version": "",
            "extra_headers": {"app_id": "appid", "api_secret": "secret"},
            "models": [{"id": "llm-m", "name": "4.0Ultra", "model": "4.0Ultra"}],
        }
    )
    resolved = resolve_llm_runtime_config(catalog=catalog, env_store=_empty_env(tmp_path))
    assert resolved.provider_name == "iflytek_spark_ws"
    assert resolved.provider_mode == "direct"
    assert resolved.api_key == "ws-key"
    assert resolved.model == "spark-x"
    assert resolved.effective_url == "https://spark-api-open.xf-yun.com/x2/"


def test_llm_legacy_iflytek_x15_binding_maps_to_http_v2(tmp_path: Path) -> None:
    catalog = _build_catalog(
        llm_profile={
            "id": "llm-p",
            "name": "LLM",
            "binding": "x1.5",
            "base_url": "https://old-http.example/v2",
            "api_key": "ws-key",
            "api_version": "",
            "extra_headers": {"app_id": "appid", "api_secret": "secret"},
            "models": [{"id": "llm-m", "name": "spark-x", "model": "spark-x"}],
        }
    )
    resolved = resolve_llm_runtime_config(catalog=catalog, env_store=_empty_env(tmp_path))
    assert resolved.provider_name == "iflytek_spark_ws"
    assert resolved.model == "spark-x"
    assert resolved.effective_url == "https://spark-api-open.xf-yun.com/v2/"


def test_llm_api_key_prefix_gateway(tmp_path: Path) -> None:
    catalog = _build_catalog(
        llm_profile={
            "id": "llm-p",
            "name": "LLM",
            "binding": "",
            "base_url": "",
            "api_key": "sk-or-test-key",
            "api_version": "",
            "extra_headers": {},
            "models": [{"id": "llm-m", "name": "m", "model": "gemini-2.5-pro"}],
        }
    )
    resolved = resolve_llm_runtime_config(catalog=catalog, env_store=_empty_env(tmp_path))
    assert resolved.provider_name == "openrouter"
    assert resolved.provider_mode == "gateway"
    assert resolved.effective_url == "https://openrouter.ai/api/v1"


def test_llm_api_base_keyword_gateway(tmp_path: Path) -> None:
    catalog = _build_catalog(
        llm_profile={
            "id": "llm-p",
            "name": "LLM",
            "binding": "",
            "base_url": "https://api.aihubmix.com/v1",
            "api_key": "k",
            "api_version": "",
            "extra_headers": {"APP-Code": "x"},
            "models": [{"id": "llm-m", "name": "m", "model": "claude-3-7-sonnet"}],
        }
    )
    resolved = resolve_llm_runtime_config(catalog=catalog, env_store=_empty_env(tmp_path))
    assert resolved.provider_name == "aihubmix"
    assert resolved.provider_mode == "gateway"
    assert resolved.effective_url == "https://api.aihubmix.com/v1"
    assert resolved.extra_headers == {"APP-Code": "x"}


def test_llm_iflytek_maas_coding_resolves_from_base_and_env_key(tmp_path: Path) -> None:
    env = _empty_env(tmp_path)
    with env.path.open("a", encoding="utf-8") as handle:
        handle.write("IFLYTEK_MAAS_API_PASSWORD=maas-password\n")

    catalog = _build_catalog(
        llm_profile={
            "id": "llm-p",
            "name": "LLM",
            "binding": "",
            "base_url": "https://maas-coding-api.cn-huabei-1.xf-yun.com/v2",
            "api_key": "",
            "api_version": "",
            "extra_headers": {},
            "models": [{"id": "llm-m", "name": "astron", "model": "astron-code-latest"}],
        }
    )
    resolved = resolve_llm_runtime_config(catalog=catalog, env_store=env)
    assert resolved.provider_name == "iflytek_maas_coding"
    assert resolved.provider_mode == "direct"
    assert resolved.model == "astron-code-latest"
    assert resolved.api_key == "maas-password"
    assert resolved.effective_url == "https://maas-coding-api.cn-huabei-1.xf-yun.com/v2"


def test_llm_local_fallback(tmp_path: Path) -> None:
    catalog = _build_catalog(
        llm_profile={
            "id": "llm-p",
            "name": "LLM",
            "binding": "",
            "base_url": "http://localhost:11434/v1",
            "api_key": "",
            "api_version": "",
            "extra_headers": {},
            "models": [{"id": "llm-m", "name": "m", "model": "llama3.2"}],
        }
    )
    resolved = resolve_llm_runtime_config(catalog=catalog, env_store=_empty_env(tmp_path))
    assert resolved.provider_name == "ollama"
    assert resolved.provider_mode == "local"
    assert resolved.api_key == "sk-no-key-required"


def test_search_fallback_to_duckduckgo_without_key(tmp_path: Path) -> None:
    catalog = _build_catalog(
        search_profile={
            "id": "search-p",
            "name": "Search",
            "provider": "brave",
            "base_url": "",
            "api_key": "",
            "proxy": "http://127.0.0.1:7890",
            "models": [],
        }
    )
    resolved = resolve_search_runtime_config(catalog=catalog, env_store=_empty_env(tmp_path))
    assert resolved.provider == "duckduckgo"
    assert resolved.requested_provider == "brave"
    assert resolved.fallback_reason is not None
    assert resolved.proxy == "http://127.0.0.1:7890"


def test_search_marks_deprecated_provider(tmp_path: Path) -> None:
    catalog = _build_catalog(
        search_profile={
            "id": "search-p",
            "name": "Search",
            "provider": "exa",
            "base_url": "",
            "api_key": "k",
            "proxy": "",
            "models": [],
        }
    )
    resolved = resolve_search_runtime_config(catalog=catalog, env_store=_empty_env(tmp_path))
    assert resolved.unsupported_provider is True
    assert resolved.deprecated_provider is True
    assert resolved.provider == "exa"


def test_search_perplexity_missing_credentials(tmp_path: Path) -> None:
    catalog = _build_catalog(
        search_profile={
            "id": "search-p",
            "name": "Search",
            "provider": "perplexity",
            "base_url": "",
            "api_key": "",
            "proxy": "",
            "models": [],
        }
    )
    resolved = resolve_search_runtime_config(catalog=catalog, env_store=_empty_env(tmp_path))
    assert resolved.provider == "perplexity"
    assert resolved.unsupported_provider is False
    assert resolved.deprecated_provider is False
    assert resolved.missing_credentials is True


def test_search_iflytek_spark_uses_api_password_env(tmp_path: Path) -> None:
    env = _empty_env(tmp_path)
    with env.path.open("a", encoding="utf-8") as handle:
        handle.write("IFLYTEK_SEARCH_API_PASSWORD=iflytek-search-password\n")
    catalog = _build_catalog(
        search_profile={
            "id": "search-p",
            "name": "Search",
            "provider": "iflytek_spark",
            "base_url": "",
            "api_key": "",
            "proxy": "",
            "models": [],
        }
    )
    resolved = resolve_search_runtime_config(catalog=catalog, env_store=env)
    assert resolved.provider == "iflytek_spark"
    assert resolved.unsupported_provider is False
    assert resolved.deprecated_provider is False
    assert resolved.missing_credentials is False
    assert resolved.api_key == "iflytek-search-password"
    assert resolved.base_url == "https://search-api-open.cn-huabei-1.xf-yun.com/v2/search"


def test_env_store_renders_shared_iflytek_credentials_to_all_iflytek_services(tmp_path: Path) -> None:
    env = _empty_env(tmp_path)
    catalog = _build_catalog(
        llm_profile={
            "id": "llm-p",
            "name": "LLM",
            "binding": "iflytek_spark_ws",
            "base_url": "https://spark-api-open.xf-yun.com/x2/",
            "api_key": "",
            "api_version": "",
            "extra_headers": {},
            "models": [{"id": "llm-m", "name": "spark-x", "model": "spark-x"}],
        },
        search_profile={
            "id": "search-p",
            "name": "Search",
            "provider": "iflytek_spark",
            "base_url": "",
            "api_key": "",
            "proxy": "",
            "models": [],
        },
    )
    catalog["provider_credentials"] = {
        "iflytek": {
            "app_id": "shared-appid",
            "api_key": "shared-ak",
            "api_secret": "shared-sk",
            "api_password": "",
        },
        "siliconflow": {"api_key": ""},
    }

    rendered = env.render_from_catalog(catalog)

    assert rendered["IFLYTEK_APPID"] == "shared-appid"
    assert rendered["IFLYTEK_API_KEY"] == "shared-ak"
    assert rendered["IFLYTEK_API_SECRET"] == "shared-sk"
    assert rendered["IFLYTEK_API_PASSWORD"] == "shared-ak:shared-sk"
    assert rendered["LLM_API_KEY"] == ""
    assert rendered["SEARCH_API_KEY"] == ""
    assert rendered["IFLYTEK_OCR_APPID"] == ""
    assert rendered["IFLYTEK_TTS_API_KEY"] == ""
    assert rendered["IFLYTEK_ASR_API_KEY"] == ""
    assert rendered["IFLYTEK_SPEECH_EVAL_API_SECRET"] == ""


def test_env_store_renders_iflytek_speech_services_from_catalog(tmp_path: Path) -> None:
    env = _empty_env(tmp_path)
    catalog = _build_catalog()
    catalog["provider_credentials"] = {
        "iflytek": {
            "app_id": "shared-appid",
            "api_key": "shared-ak",
            "api_secret": "shared-sk",
            "api_password": "",
        },
        "siliconflow": {"api_key": ""},
    }
    catalog["services"]["asr"] = {
        "active_profile_id": "asr-p",
        "profiles": [
            {
                "id": "asr-p",
                "name": "ASR",
                "provider": "iflytek",
                "base_url": "wss://iat-api.xfyun.cn/v2/iat",
                "api_key": "",
                "timeout": "45",
                "extra_headers": {
                    "language": "zh_cn",
                    "accent": "mandarin",
                    "domain": "iat",
                    "vad_eos": "2400",
                },
                "models": [],
            }
        ],
    }
    catalog["services"]["speech_eval"] = {
        "active_profile_id": "speech-eval-p",
        "profiles": [
            {
                "id": "speech-eval-p",
                "name": "Speech Evaluation",
                "provider": "iflytek",
                "base_url": "wss://ise-api.xfyun.cn/v2/open-ise",
                "api_key": "",
                "timeout": "50",
                "extra_headers": {
                    "category": "read_chapter",
                    "language": "zh_cn",
                },
                "models": [],
            }
        ],
    }

    rendered = env.render_from_catalog(catalog)

    assert rendered["SPARKWEAVE_ASR_PROVIDER"] == "iflytek"
    assert rendered["SPARKWEAVE_ASR_TIMEOUT"] == "45"
    assert rendered["IFLYTEK_ASR_API_KEY"] == ""
    assert rendered["IFLYTEK_ASR_VAD_EOS"] == "2400"
    assert rendered["SPARKWEAVE_SPEECH_EVAL_PROVIDER"] == "iflytek"
    assert rendered["SPARKWEAVE_SPEECH_EVAL_TIMEOUT"] == "50"
    assert rendered["IFLYTEK_SPEECH_EVAL_API_KEY"] == ""
    assert rendered["IFLYTEK_SPEECH_EVAL_CATEGORY"] == "read_chapter"


def test_env_store_renders_independent_iflytek_speech_credentials(tmp_path: Path) -> None:
    env = _empty_env(tmp_path)
    catalog = _build_catalog()
    catalog["provider_credentials"] = {
        "iflytek": {
            "app_id": "shared-appid",
            "api_key": "shared-ak",
            "api_secret": "shared-sk",
            "api_password": "",
        },
        "siliconflow": {"api_key": ""},
    }
    catalog["services"]["asr"] = {
        "active_profile_id": "asr-p",
        "profiles": [
            {
                "id": "asr-p",
                "name": "ASR",
                "provider": "iflytek",
                "base_url": "wss://iat-api.xfyun.cn/v2/iat",
                "api_key": "asr-ak",
                "timeout": "45",
                "extra_headers": {
                    "app_id": "asr-appid",
                    "api_secret": "asr-sk",
                    "language": "zh_cn",
                    "accent": "mandarin",
                    "domain": "iat",
                    "vad_eos": "2400",
                },
                "models": [],
            }
        ],
    }
    catalog["services"]["speech_eval"] = {
        "active_profile_id": "speech-eval-p",
        "profiles": [
            {
                "id": "speech-eval-p",
                "name": "Speech Evaluation",
                "provider": "iflytek",
                "base_url": "wss://ise-api.xfyun.cn/v2/open-ise",
                "api_key": "eval-ak",
                "timeout": "50",
                "extra_headers": {
                    "app_id": "eval-appid",
                    "api_secret": "eval-sk",
                    "category": "read_chapter",
                    "language": "zh_cn",
                },
                "models": [],
            }
        ],
    }

    rendered = env.render_from_catalog(catalog)

    assert rendered["IFLYTEK_APPID"] == "shared-appid"
    assert rendered["IFLYTEK_API_KEY"] == "shared-ak"
    assert rendered["IFLYTEK_ASR_APPID"] == "asr-appid"
    assert rendered["IFLYTEK_ASR_API_KEY"] == "asr-ak"
    assert rendered["IFLYTEK_ASR_API_SECRET"] == "asr-sk"
    assert rendered["IFLYTEK_SPEECH_EVAL_APPID"] == "eval-appid"
    assert rendered["IFLYTEK_SPEECH_EVAL_API_KEY"] == "eval-ak"
    assert rendered["IFLYTEK_SPEECH_EVAL_API_SECRET"] == "eval-sk"


def test_model_catalog_strips_only_duplicate_shared_iflytek_credentials(tmp_path: Path) -> None:
    service = ModelCatalogService(path=tmp_path / "model_catalog.json")
    catalog = _build_catalog()
    catalog["provider_credentials"] = {
        "iflytek": {
            "app_id": "shared-appid",
            "api_key": "shared-ak",
            "api_secret": "shared-sk",
            "api_password": "",
        },
        "siliconflow": {"api_key": ""},
    }
    catalog["services"]["asr"] = {
        "active_profile_id": "asr-p",
        "profiles": [
            {
                "id": "asr-p",
                "name": "ASR",
                "provider": "iflytek",
                "base_url": "wss://iat-api.xfyun.cn/v2/iat",
                "api_key": "asr-ak",
                "extra_headers": {"app_id": "asr-appid", "api_secret": "asr-sk"},
                "models": [],
            }
        ],
    }
    catalog["services"]["speech_eval"] = {
        "active_profile_id": "speech-eval-p",
        "profiles": [
            {
                "id": "speech-eval-p",
                "name": "Speech Evaluation",
                "provider": "iflytek",
                "base_url": "wss://ise-api.xfyun.cn/v2/open-ise",
                "api_key": "shared-ak",
                "extra_headers": {"app_id": "shared-appid", "api_secret": "shared-sk"},
                "models": [],
            }
        ],
    }

    changed = service._strip_shared_credentials_from_profiles(catalog)

    asr = catalog["services"]["asr"]["profiles"][0]
    speech_eval = catalog["services"]["speech_eval"]["profiles"][0]
    assert changed is True
    assert asr["api_key"] == "asr-ak"
    assert asr["extra_headers"]["app_id"] == "asr-appid"
    assert asr["extra_headers"]["api_secret"] == "asr-sk"
    assert speech_eval["api_key"] == ""
    assert speech_eval["extra_headers"]["app_id"] == ""
    assert speech_eval["extra_headers"]["api_secret"] == ""


def test_env_store_renders_iflytek_visual_services_from_catalog(tmp_path: Path) -> None:
    env = _empty_env(tmp_path)
    catalog = _build_catalog()
    catalog["provider_credentials"] = {
        "iflytek": {
            "app_id": "shared-appid",
            "api_key": "shared-ak",
            "api_secret": "shared-sk",
            "api_password": "",
        },
        "siliconflow": {"api_key": ""},
    }
    catalog["services"]["formula_ocr"] = {
        "active_profile_id": "formula-p",
        "profiles": [
            {
                "id": "formula-p",
                "name": "Formula",
                "provider": "iflytek",
                "base_url": "https://rest-api.xfyun.cn/v2/itr",
                "api_key": "",
                "timeout": "35",
                "extra_headers": {
                    "app_id": "",
                    "api_secret": "",
                    "ent": "teach-photo-hand",
                    "aue": "raw",
                },
                "models": [],
            }
        ],
    }
    catalog["services"]["image_understanding"] = {
        "active_profile_id": "image-p",
        "profiles": [
            {
                "id": "image-p",
                "name": "Image",
                "provider": "iflytek",
                "base_url": "wss://spark-api.cn-huabei-1.xf-yun.com/v2.1/image",
                "api_key": "",
                "timeout": "50",
                "extra_headers": {
                    "app_id": "",
                    "api_secret": "",
                    "protocol": "spark_image",
                    "domain": "imagev3",
                    "max_tokens": "1024",
                    "temperature": "0.1",
                    "top_k": "3",
                    "uid": "sparkweave-test",
                },
                "models": [],
            }
        ],
    }

    rendered = env.render_from_catalog(catalog)

    assert rendered["SPARKWEAVE_FORMULA_OCR_PROVIDER"] == "iflytek"
    assert rendered["IFLYTEK_FORMULA_API_KEY"] == ""
    assert rendered["IFLYTEK_FORMULA_ENT"] == "teach-photo-hand"
    assert rendered["IFLYTEK_FORMULA_TIMEOUT"] == "35"
    assert rendered["SPARKWEAVE_IMAGE_UNDERSTANDING_PROVIDER"] == "iflytek"
    assert rendered["IFLYTEK_VISION_API_KEY"] == ""
    assert rendered["IFLYTEK_VISION_MAX_TOKENS"] == "1024"
    assert rendered["IFLYTEK_VISION_UID"] == "sparkweave-test"


def test_env_store_renders_shared_siliconflow_key_to_ocr_and_embedding(tmp_path: Path) -> None:
    env = _empty_env(tmp_path)
    catalog = _build_catalog()
    catalog["provider_credentials"] = {
        "iflytek": {"app_id": "", "api_key": "", "api_secret": "", "api_password": ""},
        "siliconflow": {"api_key": "sf-shared"},
    }
    catalog["services"]["embedding"] = {
        "active_profile_id": "embedding-p",
        "active_model_id": "embedding-m",
        "profiles": [
            {
                "id": "embedding-p",
                "name": "Embedding",
                "binding": "openai",
                "base_url": "https://api.siliconflow.cn/v1/embeddings",
                "api_key": "",
                "api_version": "",
                "extra_headers": {},
                "models": [
                    {
                        "id": "embedding-m",
                        "name": "Qwen/Qwen3-Embedding-8B",
                        "model": "Qwen/Qwen3-Embedding-8B",
                        "dimension": "4096",
                    }
                ],
            }
        ],
    }
    catalog["services"]["ocr"] = {
        "active_profile_id": "ocr-p",
        "profiles": [
            {
                "id": "ocr-p",
                "name": "OCR",
                "provider": "siliconflow",
                "strategy": "auto",
                "base_url": "https://api.siliconflow.cn/v1",
                "api_key": "",
                "timeout": "30",
                "max_pages": "20",
                "dpi": "180",
                "min_text_chars": "80",
                "extra_headers": {"model": "deepseek-ai/DeepSeek-OCR"},
                "models": [],
            }
        ],
    }

    rendered = env.render_from_catalog(catalog)

    assert rendered["SILICONFLOW_API_KEY"] == "sf-shared"
    assert rendered["EMBEDDING_API_KEY"] == ""
    assert rendered["SILICONFLOW_OCR_API_KEY"] == ""


def test_search_iflytek_spark_missing_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for env_name in (
        "IFLYTEK_SEARCH_API_PASSWORD",
        "IFLYTEK_SPARK_SEARCH_API_PASSWORD",
        "XFYUN_SEARCH_API_PASSWORD",
        "IFLYTEK_SEARCH_APIPASSWORD",
    ):
        monkeypatch.delenv(env_name, raising=False)
    catalog = _build_catalog(
        search_profile={
            "id": "search-p",
            "name": "Search",
            "provider": "iflytek_spark",
            "base_url": "",
            "api_key": "",
            "proxy": "",
            "models": [],
        }
    )
    resolved = resolve_search_runtime_config(catalog=catalog, env_store=_empty_env(tmp_path))
    assert resolved.provider == "iflytek_spark"
    assert resolved.unsupported_provider is False
    assert resolved.missing_credentials is True


def test_env_store_renders_ocr_catalog_settings(tmp_path: Path) -> None:
    env = _empty_env(tmp_path)
    catalog = _build_catalog()
    catalog["services"]["ocr"] = {
        "active_profile_id": "ocr-p",
        "profiles": [
            {
                "id": "ocr-p",
                "name": "OCR",
                "provider": "iflytek",
                "strategy": "iflytek_first",
                "base_url": "https://cbm01.cn-huabei-1.xf-yun.com/v1/private/se75ocrbm",
                "api_key": "ocr-key",
                "timeout": "45",
                "max_pages": "12",
                "dpi": "200",
                "min_text_chars": "40",
                "extra_headers": {
                    "app_id": "ocr-app",
                    "api_secret": "ocr-secret",
                    "service_id": "se75ocrbm",
                    "category": "ch_en_public_cloud",
                },
                "models": [],
            }
        ],
    }

    rendered = env.render_from_catalog(catalog)

    assert rendered["SPARKWEAVE_OCR_PROVIDER"] == "iflytek"
    assert rendered["SPARKWEAVE_PDF_OCR_STRATEGY"] == "iflytek_first"
    assert rendered["SPARKWEAVE_OCR_TIMEOUT"] == "45"
    assert rendered["SPARKWEAVE_OCR_MAX_PAGES"] == "12"
    assert rendered["SPARKWEAVE_OCR_DPI"] == "200"
    assert rendered["SPARKWEAVE_OCR_MIN_TEXT_CHARS"] == "40"
    assert rendered["IFLYTEK_OCR_APPID"] == "ocr-app"
    assert rendered["IFLYTEK_OCR_API_KEY"] == "ocr-key"
    assert rendered["IFLYTEK_OCR_API_SECRET"] == "ocr-secret"


def test_env_store_does_not_force_optional_ocr_knobs(tmp_path: Path) -> None:
    env = _empty_env(tmp_path)
    catalog = _build_catalog()
    catalog["services"]["ocr"] = {
        "active_profile_id": "ocr-p",
        "profiles": [
            {
                "id": "ocr-p",
                "name": "OCR",
                "provider": "iflytek",
                "strategy": "auto",
                "base_url": "https://cbm01.cn-huabei-1.xf-yun.com/v1/private/se75ocrbm",
                "api_key": "ocr-key",
                "extra_headers": {
                    "app_id": "ocr-app",
                    "api_secret": "ocr-secret",
                },
                "models": [],
            }
        ],
    }

    rendered = env.render_from_catalog(catalog)

    assert rendered["SPARKWEAVE_OCR_TIMEOUT"] == ""
    assert rendered["SPARKWEAVE_OCR_MAX_PAGES"] == ""
    assert rendered["SPARKWEAVE_OCR_DPI"] == ""
    assert rendered["SPARKWEAVE_OCR_MIN_TEXT_CHARS"] == ""


def test_env_store_renders_siliconflow_ocr_catalog_settings(tmp_path: Path) -> None:
    env = _empty_env(tmp_path)
    catalog = _build_catalog()
    catalog["services"]["ocr"] = {
        "active_profile_id": "ocr-p",
        "profiles": [
            {
                "id": "ocr-p",
                "name": "OCR",
                "provider": "siliconflow",
                "strategy": "ocr_first",
                "base_url": "https://api.siliconflow.cn/v1",
                "api_key": "sf-key",
                "timeout": "60",
                "max_pages": "8",
                "dpi": "220",
                "min_text_chars": "20",
                "extra_headers": {
                    "model": "deepseek-ai/DeepSeek-OCR",
                    "prompt": "只输出文字",
                },
                "models": [],
            }
        ],
    }

    rendered = env.render_from_catalog(catalog)

    assert rendered["SPARKWEAVE_OCR_PROVIDER"] == "siliconflow"
    assert rendered["SPARKWEAVE_PDF_OCR_STRATEGY"] == "ocr_first"
    assert rendered["SILICONFLOW_OCR_API_KEY"] == "sf-key"
    assert rendered["SILICONFLOW_OCR_BASE_URL"] == "https://api.siliconflow.cn/v1"
    assert rendered["SILICONFLOW_OCR_MODEL"] == "deepseek-ai/DeepSeek-OCR"
    assert rendered["SILICONFLOW_OCR_PROMPT"] == "只输出文字"
    assert rendered["IFLYTEK_OCR_API_KEY"] == ""


def test_env_store_renders_tts_catalog_settings(tmp_path: Path) -> None:
    env = _empty_env(tmp_path)
    catalog = _build_catalog()
    catalog["services"]["tts"] = {
        "active_profile_id": "tts-p",
        "profiles": [
            {
                "id": "tts-p",
                "name": "TTS",
                "provider": "iflytek",
                "base_url": "wss://cbm01.cn-huabei-1.xf-yun.com/v1/private/mcd9m97e6",
                "api_key": "tts-key",
                "timeout": "35",
                "extra_headers": {
                    "app_id": "tts-app",
                    "api_secret": "tts-secret",
                    "voice": "x5_lingxiaoxuan_flow",
                    "encoding": "lame",
                    "sample_rate": "24000",
                    "channels": "1",
                    "bit_depth": "16",
                    "frame_size": "0",
                    "speed": "55",
                    "volume": "60",
                    "pitch": "45",
                },
                "models": [],
            }
        ],
    }

    rendered = env.render_from_catalog(catalog)

    assert rendered["SPARKWEAVE_TTS_PROVIDER"] == "iflytek"
    assert rendered["SPARKWEAVE_TTS_TIMEOUT"] == "35"
    assert rendered["IFLYTEK_TTS_APPID"] == "tts-app"
    assert rendered["IFLYTEK_TTS_API_KEY"] == "tts-key"
    assert rendered["IFLYTEK_TTS_API_SECRET"] == "tts-secret"
    assert rendered["IFLYTEK_TTS_URL"] == "wss://cbm01.cn-huabei-1.xf-yun.com/v1/private/mcd9m97e6"
    assert rendered["IFLYTEK_TTS_VOICE"] == "x5_lingxiaoxuan_flow"
    assert rendered["IFLYTEK_TTS_SAMPLE_RATE"] == "24000"
    assert rendered["IFLYTEK_TTS_SPEED"] == "55"
    assert rendered["IFLYTEK_TTS_VOLUME"] == "60"
    assert rendered["IFLYTEK_TTS_PITCH"] == "45"


def test_search_serper_missing_credentials(tmp_path: Path) -> None:
    catalog = _build_catalog(
        search_profile={
            "id": "search-p",
            "name": "Search",
            "provider": "serper",
            "base_url": "",
            "api_key": "",
            "proxy": "",
            "models": [],
        }
    )
    resolved = resolve_search_runtime_config(catalog=catalog, env_store=_empty_env(tmp_path))
    assert resolved.provider == "serper"
    assert resolved.unsupported_provider is False
    assert resolved.deprecated_provider is False
    assert resolved.missing_credentials is True


def test_search_searxng_without_url_fallback(tmp_path: Path) -> None:
    catalog = _build_catalog(
        search_profile={
            "id": "search-p",
            "name": "Search",
            "provider": "searxng",
            "base_url": "",
            "api_key": "",
            "proxy": "",
            "models": [],
        }
    )
    resolved = resolve_search_runtime_config(catalog=catalog, env_store=_empty_env(tmp_path))
    assert resolved.provider == "duckduckgo"
    assert resolved.fallback_reason is not None


