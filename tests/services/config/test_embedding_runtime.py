"""Tests for normalized embedding runtime resolution."""

from __future__ import annotations

from pathlib import Path

from sparkweave.services import config as config_module
from sparkweave.services.config import EnvStore, ModelCatalogService, resolve_embedding_runtime_config


def _build_catalog(
    *,
    embedding_profile: dict | None = None,
    embedding_model: dict | None = None,
) -> dict:
    embedding_profile = embedding_profile or {
        "id": "embedding-p",
        "name": "Embedding",
        "binding": "openai",
        "base_url": "",
        "api_key": "",
        "api_version": "",
        "extra_headers": {},
        "models": [{"id": "embedding-m", "name": "m", "model": "text-embedding-3-large"}],
    }
    embedding_model = embedding_model or embedding_profile["models"][0]
    return {
        "version": 1,
        "services": {
            "llm": {"active_profile_id": None, "active_model_id": None, "profiles": []},
            "embedding": {
                "active_profile_id": embedding_profile["id"],
                "active_model_id": embedding_model["id"],
                "profiles": [embedding_profile],
            },
            "search": {"active_profile_id": None, "profiles": []},
        },
    }


def _env(tmp_path: Path, lines: list[str]) -> EnvStore:
    defaults = [
        "EMBEDDING_BINDING=",
        "EMBEDDING_MODEL=",
        "EMBEDDING_API_KEY=",
        "EMBEDDING_HOST=",
        "EMBEDDING_DIMENSION=",
        "EMBEDDING_API_VERSION=",
        "OPENAI_API_KEY=",
        "AZURE_OPENAI_API_KEY=",
        "AZURE_API_KEY=",
        "COHERE_API_KEY=",
        "JINA_API_KEY=",
        "SILICONFLOW_API_KEY=",
        "IFLYTEK_EMBEDDING_APPID=",
        "IFLYTEK_EMBEDDING_API_KEY=",
        "IFLYTEK_EMBEDDING_API_SECRET=",
        "IFLYTEK_SPARK_EMBEDDING_API_KEY=",
        "IFLYTEK_SPARK_EMBEDDING_API_SECRET=",
        "XFYUN_EMBEDDING_API_KEY=",
        "XFYUN_EMBEDDING_API_SECRET=",
        "SPARK_EMBEDDING_API_KEY=",
        "SPARK_EMBEDDING_API_SECRET=",
        "IFLYTEK_EMBEDDING_DOMAIN=",
        "HOSTED_VLLM_API_KEY=",
    ]
    env_path = tmp_path / ".env"
    env_path.write_text("\n".join(defaults + lines) + "\n", encoding="utf-8")
    return EnvStore(path=env_path)


def test_embedding_explicit_binding_and_headers(tmp_path: Path) -> None:
    catalog = _build_catalog(
        embedding_profile={
            "id": "embedding-p",
            "name": "Embedding",
            "binding": "jina",
            "base_url": "",
            "api_key": "jina-key",
            "api_version": "",
            "extra_headers": {"X-App": "demo"},
            "models": [
                {
                    "id": "embedding-m",
                    "name": "jina",
                    "model": "jina-embeddings-v3",
                    "dimension": "1024",
                }
            ],
        }
    )
    env = _env(
        tmp_path,
        [
            "EMBEDDING_BINDING=",
            "EMBEDDING_MODEL=",
            "EMBEDDING_API_KEY=",
            "EMBEDDING_HOST=",
            "EMBEDDING_DIMENSION=",
            "EMBEDDING_API_VERSION=",
        ],
    )
    resolved = resolve_embedding_runtime_config(catalog=catalog, env_store=env)
    assert resolved.provider_name == "jina"
    assert resolved.provider_mode == "standard"
    assert resolved.effective_url == "https://api.jina.ai/v1"
    assert resolved.extra_headers == {"X-App": "demo"}
    assert resolved.dimension == 1024


def test_embedding_alias_canonicalization_google_to_openai(tmp_path: Path) -> None:
    catalog = _build_catalog(
        embedding_profile={
            "id": "embedding-p",
            "name": "Embedding",
            "binding": "google",
            "base_url": "",
            "api_key": "k",
            "api_version": "",
            "extra_headers": {},
            "models": [{"id": "embedding-m", "name": "m", "model": "text-embedding-3-small"}],
        }
    )
    resolved = resolve_embedding_runtime_config(catalog=catalog, env_store=_env(tmp_path, []))
    assert resolved.provider_name == "openai"
    assert resolved.binding == "openai"


def test_env_file_overrides_stale_process_embedding_env(
    tmp_path: Path,
    monkeypatch,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "EMBEDDING_BINDING=siliconflow",
                "EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B",
                "EMBEDDING_HOST=https://api.siliconflow.cn/v1",
                "EMBEDDING_DIMENSION=4096",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_module, "ENV_PATH", env_path)
    monkeypatch.setenv("EMBEDDING_BINDING", "iflytek_spark")
    monkeypatch.setenv("EMBEDDING_MODEL", "llm-embedding")
    monkeypatch.setenv("EMBEDDING_HOST", "https://emb-cn-huabei-1.xf-yun.com/")
    monkeypatch.setenv("EMBEDDING_DIMENSION", "2560")

    env = EnvStore(path=env_path)
    summary = env.as_summary()

    assert env.get("EMBEDDING_BINDING") == "siliconflow"
    assert summary.embedding["binding"] == "siliconflow"
    assert summary.embedding["model"] == "Qwen/Qwen3-Embedding-8B"
    assert summary.embedding["dimension"] == "4096"


def test_existing_catalog_is_not_overwritten_by_stale_env_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "EMBEDDING_BINDING=iflytek_spark",
                "EMBEDDING_MODEL=llm-embedding",
                "EMBEDDING_HOST=https://emb-cn-huabei-1.xf-yun.com/",
                "EMBEDDING_DIMENSION=2560",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    catalog_path = tmp_path / "model_catalog.json"
    catalog_path.write_text(
        """
{
  "version": 1,
  "services": {
    "embedding": {
      "active_profile_id": "embedding-p",
      "active_model_id": "embedding-m",
      "profiles": [
        {
          "id": "embedding-p",
          "name": "Embedding",
          "binding": "siliconflow",
          "base_url": "https://api.siliconflow.cn/v1",
          "api_key": "",
          "api_version": "",
          "extra_headers": {},
          "models": [
            {
              "id": "embedding-m",
              "name": "Qwen/Qwen3-Embedding-8B",
              "model": "Qwen/Qwen3-Embedding-8B",
              "dimension": "4096"
            }
          ]
        }
      ]
    }
  }
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(config_module, "_env_store", EnvStore(path=env_path))

    loaded = ModelCatalogService(path=catalog_path).load()
    profile = loaded["services"]["embedding"]["profiles"][0]
    model = profile["models"][0]

    assert profile["binding"] == "siliconflow"
    assert profile["base_url"] == "https://api.siliconflow.cn/v1"
    assert model["model"] == "Qwen/Qwen3-Embedding-8B"
    assert model["dimension"] == "4096"


def test_embedding_local_fallback_from_base_url(tmp_path: Path) -> None:
    catalog = _build_catalog(
        embedding_profile={
            "id": "embedding-p",
            "name": "Embedding",
            "binding": "",
            "base_url": "http://localhost:11434",
            "api_key": "",
            "api_version": "",
            "extra_headers": {},
            "models": [{"id": "embedding-m", "name": "m", "model": "nomic-embed-text"}],
        }
    )
    resolved = resolve_embedding_runtime_config(catalog=catalog, env_store=_env(tmp_path, []))
    assert resolved.provider_name == "ollama"
    assert resolved.provider_mode == "local"
    assert resolved.api_key == "sk-no-key-required"


def test_embedding_openai_default_base_injected(tmp_path: Path) -> None:
    catalog = _build_catalog(
        embedding_profile={
            "id": "embedding-p",
            "name": "Embedding",
            "binding": "openai",
            "base_url": "",
            "api_key": "sk-test",
            "api_version": "",
            "extra_headers": {},
            "models": [{"id": "embedding-m", "name": "m", "model": "text-embedding-3-large"}],
        }
    )
    resolved = resolve_embedding_runtime_config(catalog=catalog, env_store=_env(tmp_path, []))
    assert resolved.provider_name == "openai"
    assert resolved.effective_url == "https://api.openai.com/v1"


def test_embedding_provider_env_key_fallback(tmp_path: Path) -> None:
    catalog = _build_catalog(
        embedding_profile={
            "id": "embedding-p",
            "name": "Embedding",
            "binding": "cohere",
            "base_url": "",
            "api_key": "",
            "api_version": "",
            "extra_headers": {},
            "models": [{"id": "embedding-m", "name": "m", "model": "embed-v4.0"}],
        }
    )
    env = _env(
        tmp_path,
        [
            "COHERE_API_KEY=cohere-test-key",
            "EMBEDDING_BINDING=",
            "EMBEDDING_MODEL=",
            "EMBEDDING_API_KEY=",
            "EMBEDDING_HOST=",
            "EMBEDDING_DIMENSION=",
            "EMBEDDING_API_VERSION=",
        ],
    )
    resolved = resolve_embedding_runtime_config(catalog=catalog, env_store=env)
    assert resolved.provider_name == "cohere"
    assert resolved.api_key == "cohere-test-key"


def test_embedding_siliconflow_shared_credentials(tmp_path: Path) -> None:
    catalog = _build_catalog(
        embedding_profile={
            "id": "embedding-p",
            "name": "Embedding",
            "binding": "siliconflow",
            "base_url": "",
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
    )
    catalog["provider_credentials"] = {"siliconflow": {"api_key": "sf-shared"}}

    resolved = resolve_embedding_runtime_config(catalog=catalog, env_store=_env(tmp_path, []))

    assert resolved.provider_name == "siliconflow"
    assert resolved.binding == "siliconflow"
    assert resolved.effective_url == "https://api.siliconflow.cn/v1"
    assert resolved.api_key == "sf-shared"
    assert resolved.dimension == 4096


def test_embedding_iflytek_spark_provider_defaults(tmp_path: Path) -> None:
    catalog = _build_catalog(
        embedding_profile={
            "id": "embedding-p",
            "name": "Embedding",
            "binding": "iflytek_spark",
            "base_url": "",
            "api_key": "",
            "api_version": "",
            "extra_headers": {},
            "models": [{"id": "embedding-m", "name": "m", "model": "llm-embedding", "dimension": "2560"}],
        }
    )
    env = _env(
        tmp_path,
        [
            "IFLYTEK_EMBEDDING_APPID=iflytek-appid",
            "IFLYTEK_EMBEDDING_API_KEY=iflytek-embedding-key",
            "IFLYTEK_EMBEDDING_API_SECRET=iflytek-secret",
        ],
    )
    resolved = resolve_embedding_runtime_config(catalog=catalog, env_store=env)
    assert resolved.provider_name == "iflytek_spark"
    assert resolved.effective_url == "https://emb-cn-huabei-1.xf-yun.com/"
    assert resolved.api_key == "iflytek-embedding-key"
    assert resolved.dimension == 2560
    assert resolved.extra_headers["app_id"] == "iflytek-appid"
    assert resolved.extra_headers["api_secret"] == "iflytek-secret"
    assert resolved.extra_headers["domain"] == "para"


def test_embedding_iflytek_alias_canonicalization(tmp_path: Path) -> None:
    catalog = _build_catalog(
        embedding_profile={
            "id": "embedding-p",
            "name": "Embedding",
            "binding": "xfyun_embedding",
            "base_url": "",
            "api_key": "iflytek-key",
            "api_version": "",
            "extra_headers": {},
            "models": [{"id": "embedding-m", "name": "m", "model": "llm-embedding", "dimension": "2560"}],
        }
    )
    resolved = resolve_embedding_runtime_config(catalog=catalog, env_store=_env(tmp_path, []))
    assert resolved.provider_name == "iflytek_spark"
    assert resolved.binding == "iflytek_spark"


