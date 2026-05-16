"""Lightweight diagnostics for RAG vector storage."""

from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
from typing import Any
from urllib.parse import urlparse

from sparkweave.services.embedding_support import get_embedding_config
from sparkweave.services.rag_support import milvus_http
from sparkweave.services.rag_support.factory import DEFAULT_PROVIDER, normalize_provider_name

MILVUS_MARKER_SCHEMA_VERSION = 1


def _env_value(name: str, default: str = "") -> str:
    try:
        from sparkweave.services.config import get_env_store

        return get_env_store().get(name, default)
    except Exception:
        return os.getenv(name, default)


def _env_float(name: str, default: float) -> float:
    raw = _env_value(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def default_milvus_uri() -> str:
    """Return the platform-aware Milvus default without importing LlamaIndex."""
    if platform.system().lower() == "windows":
        return "http://localhost:19530"
    return "./data/milvus/sparkweave.db"


def is_local_file_uri(uri: str) -> bool:
    return "://" not in uri and uri != ":memory:"


def _read_marker(kb_base_dir: str | Path, kb_name: str | None) -> dict[str, Any]:
    if not kb_name:
        return {}
    marker = Path(kb_base_dir) / kb_name / "milvus_storage" / "metadata.json"
    if not marker.exists():
        return {}
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_marker_error": str(exc)}
    return data if isinstance(data, dict) else {}


def _read_kb_provider(kb_base_dir: str | Path, kb_name: str | None) -> str | None:
    if not kb_name:
        return None
    config_path = Path(kb_base_dir) / "kb_config.json"
    if not config_path.exists():
        return None
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    knowledge_bases = data.get("knowledge_bases")
    if not isinstance(knowledge_bases, dict):
        return None
    entry = knowledge_bases.get(kb_name)
    if not isinstance(entry, dict):
        return None
    raw_provider = entry.get("rag_provider")
    return normalize_provider_name(raw_provider) if raw_provider else None


def _has_legacy_storage(kb_base_dir: str | Path, kb_name: str | None) -> bool:
    if not kb_name:
        return False
    return (Path(kb_base_dir) / kb_name / "llamaindex_storage").exists()


def _embedding_snapshot() -> dict[str, Any]:
    try:
        config = get_embedding_config()
        return {
            "embedding_model": config.model,
            "embedding_dim": config.dim,
        }
    except Exception as exc:
        return {
            "embedding_status": "error",
            "embedding_error": str(exc),
        }


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _proxy_snapshot(uri: str) -> dict[str, Any]:
    http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy") or ""
    https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy") or ""
    no_proxy = os.getenv("NO_PROXY") or os.getenv("no_proxy") or ""
    bypassed = milvus_http.should_bypass_proxy(uri) if milvus_http.is_http_uri(uri) else False
    return {
        "http_proxy_configured": bool(http_proxy),
        "https_proxy_configured": bool(https_proxy),
        "no_proxy": no_proxy,
        "milvus_proxy_bypassed": bypassed,
    }


def _connection_error_kind(message: str) -> str:
    normalized = message.lower()
    if "10061" in normalized or "connection refused" in normalized or "actively refused" in normalized:
        return "connection_refused"
    if "timed out" in normalized or "timeout" in normalized:
        return "timeout"
    if "name or service not known" in normalized or "nodename nor servname" in normalized:
        return "dns_failed"
    if "http 502" in normalized or "bad gateway" in normalized:
        return "bad_gateway"
    return "unknown"


def _runtime_action_for_error(error_kind: str, *, uri: str, uri_mismatch: bool) -> str:
    if error_kind == "connection_refused":
        if uri_mismatch:
            return (
                "先启动当前运行模式对应的 Milvus，再保持 `MILVUS_URI` 与建库地址一致；"
                "本机开发可运行 `python scripts/start_docker.py --milvus-only`，必要时重建索引。"
            )
        return "启动 Milvus 后重试；本机开发可运行 `python scripts/start_docker.py --milvus-only`。"
    if error_kind == "bad_gateway":
        if uri_mismatch:
            return "检查代理、端口映射或网关配置，并确认 `MILVUS_URI` 与建库时的 Milvus 地址一致。"
        return "检查代理、端口映射或网关配置；本地 Milvus 地址应绕过 HTTP 代理。"
    if error_kind == "timeout":
        return "确认 Milvus 服务已启动且网络可达，必要时提高 `RAG_DIAGNOSTICS_TIMEOUT_SECONDS`。"
    if error_kind == "dns_failed":
        return "确认当前运行模式能解析 Milvus 主机名；Docker 内使用 `milvus`，本机使用 `localhost`。"
    return "检查 Milvus、Embedding 服务和网络连接。"


def _docker_snapshot(timeout_seconds: float = 3.0) -> dict[str, Any]:
    docker = shutil.which("docker")
    if not docker:
        return {
            "docker_cli_present": False,
            "docker_running": False,
            "error": "Docker CLI was not found on PATH.",
        }
    try:
        completed = subprocess.run(
            [docker, "info", "--format", "{{json .ServerVersion}}"],
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return {
            "docker_cli_present": True,
            "docker_running": False,
            "error": "Docker did not respond before the preflight timeout.",
        }
    except OSError as exc:
        return {
            "docker_cli_present": True,
            "docker_running": False,
            "error": str(exc),
        }
    return {
        "docker_cli_present": True,
        "docker_running": completed.returncode == 0,
        "server_version": completed.stdout.strip().strip('"') if completed.returncode == 0 else "",
        "error": completed.stderr.strip() if completed.returncode != 0 else "",
    }


def _milvus_uri_mismatch_hint(indexed_uri: str, runtime_uri: str) -> dict[str, str]:
    """Explain common Milvus URI mismatches in user-facing terms."""
    indexed = urlparse(indexed_uri)
    runtime = urlparse(runtime_uri)
    indexed_host = (indexed.hostname or "").lower()
    runtime_host = (runtime.hostname or "").lower()
    indexed_port = indexed.port
    runtime_port = runtime.port

    if indexed_host == "milvus" and runtime_host in {"localhost", "127.0.0.1", "::1"}:
        return {
            "kind": "docker_marker_host_runtime",
            "summary": (
                "这个知识库是在 Docker Compose 内部地址 `http://milvus:19530` 下建立的，"
                "当前后端正在用主机地址访问 Milvus。"
            ),
            "primary_action": (
                "保持后端和 Milvus 在同一种运行模式下使用；如果连接失败，改好 "
                "`MILVUS_URI` 后重建索引。"
            ),
        }
    if runtime_host == "milvus" and indexed_host in {"localhost", "127.0.0.1", "::1"}:
        return {
            "kind": "host_marker_docker_runtime",
            "summary": (
                "这个知识库是在主机 Milvus 地址下建立的，当前后端正在 Docker 网络内使用服务名访问。"
            ),
            "primary_action": (
                "确认 Compose 中 `DOCKER_MILVUS_URI` 指向同一个 Milvus 实例；必要时在容器模式下重建索引。"
            ),
        }
    if indexed_port and runtime_port and indexed_port != runtime_port:
        return {
            "kind": "port_mismatch",
            "summary": "知识库记录的 Milvus 端口与当前运行时端口不一致。",
            "primary_action": "确认 `MILVUS_URI`、`MILVUS_PORT` 和实际 Milvus 服务端口一致后重建索引。",
        }
    return {
        "kind": "uri_mismatch",
        "summary": "知识库记录的 Milvus 地址与当前运行时地址不一致。",
        "primary_action": "确认当前后端连接的是建库时同一个 Milvus 实例；如果不是，请重建索引。",
    }


def _marker_embedding_check(marker: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    indexed_model = str(marker.get("embedding_model") or "").strip()
    indexed_dim = _coerce_int(marker.get("embedding_dim"))
    current_model = str(current.get("embedding_model") or "").strip()
    current_dim = _coerce_int(current.get("embedding_dim"))
    model_mismatch = bool(indexed_model and current_model and indexed_model != current_model)
    dim_mismatch = indexed_dim is not None and current_dim is not None and indexed_dim != current_dim
    return {
        "indexed_embedding_model": indexed_model or None,
        "indexed_embedding_dim": indexed_dim,
        "current_embedding_model": current_model or None,
        "current_embedding_dim": current_dim,
        "embedding_mismatch": model_mismatch or dim_mismatch,
        "embedding_model_mismatch": model_mismatch,
        "embedding_dim_mismatch": dim_mismatch,
    }


def _set_warning(result: dict[str, Any]) -> None:
    if result.get("status") != "error":
        result["status"] = "warning"


def _with_readiness(result: dict[str, Any]) -> dict[str, Any]:
    """Attach a user-facing readiness summary without changing raw checks."""
    provider = str(result.get("provider") or DEFAULT_PROVIDER)
    status = str(result.get("status") or "configured")
    marker_present = bool(result.get("marker_present"))
    legacy_storage = bool(result.get("legacy_storage_present"))
    vector_rows = _coerce_int(result.get("vector_row_count"))
    embedding_mismatch = bool(result.get("embedding_mismatch"))
    collection_present = result.get("collection_present")
    uri_mismatch = bool(result.get("uri_mismatch"))

    if status == "error" and uri_mismatch:
        state = "error"
        label = "地址不一致"
        summary = (
            "RAG 连接失败，并且知识库记录的 Milvus 地址与当前运行时不一致。"
            f"{result.get('uri_mismatch_summary') or ''}"
        )
        action = str(
            result.get("runtime_action")
            or result.get("uri_mismatch_action")
            or "统一 Milvus 运行模式后重建索引。"
        )
    elif status == "error":
        state = "error"
        error_kind = str(result.get("connection_error_kind") or "")
        label = "服务未启动" if error_kind == "connection_refused" else "连接异常"
        summary = (
            "当前运行地址没有可用的 Milvus 服务，聊天会缺少知识库证据。"
            if error_kind == "connection_refused"
            else "RAG 后端暂时不可用，聊天会缺少知识库证据。"
        )
        action = str(result.get("runtime_action") or "检查 Milvus、Embedding 服务和网络连接。")
    elif provider != DEFAULT_PROVIDER:
        state = "ready"
        label = "本地索引"
        summary = "当前知识库使用本地 LlamaIndex 兼容索引，可以用于检索。"
        action = "如需生产级向量库能力，可重建到 Milvus。"
    elif legacy_storage and not marker_present:
        state = "legacy"
        label = "需要迁移"
        summary = "检测到旧版本地索引，但当前默认检索使用 Milvus。"
        action = "在知识库页面执行重建索引。"
    elif not marker_present:
        state = "not_indexed"
        label = "尚未索引"
        summary = "这个知识库还没有可用的 Milvus 索引。"
        action = "上传资料并等待索引完成，或手动重建索引。"
    elif embedding_mismatch:
        state = "attention"
        label = "需要重建"
        summary = "知识库的向量模型与当前 Embedding 配置不一致。"
        action = "用当前 Embedding 配置重建索引。"
    elif vector_rows == 0:
        state = "attention"
        label = "没有向量"
        summary = "Milvus collection 存在，但没有可检索的向量数据。"
        action = "重新上传或重建索引，并确认解析后的文档不为空。"
    elif collection_present is False:
        state = "attention"
        label = "集合缺失"
        summary = "元数据存在，但 Milvus 中没有找到对应 collection。"
        action = "检查 Milvus 地址是否变化，必要时重建索引。"
    elif uri_mismatch:
        state = "attention"
        label = "地址不一致"
        summary = str(
            result.get("uri_mismatch_summary")
            or "知识库记录的 Milvus 地址与当前运行时地址不一致。"
        )
        action = str(
            result.get("uri_mismatch_action")
            or "确认当前后端连接的是建库时同一个 Milvus 实例；如果不是，请重建索引。"
        )
    elif status == "warning":
        state = "attention"
        label = "可用但需关注"
        summary = "RAG 基本可用，但诊断发现需要关注的配置或元数据问题。"
        action = "查看诊断检查项，按提示处理。"
    else:
        state = "ready"
        label = "检索就绪"
        rows_text = f"{vector_rows} 条向量" if vector_rows is not None else "向量数据"
        summary = f"知识库已连接并可检索，当前可见 {rows_text}。"
        action = "可以在聊天中启用知识库问答。"

    result["readiness"] = {
        "state": state,
        "label": label,
        "summary": summary,
        "primary_action": action,
    }
    return result


def diagnose_rag(
    *,
    kb_base_dir: str | Path,
    kb_name: str | None = None,
    check_connection: bool = True,
) -> dict[str, Any]:
    """Return a machine-readable RAG diagnostic snapshot."""
    kb_provider = _read_kb_provider(kb_base_dir, kb_name)
    provider = kb_provider or normalize_provider_name(_env_value("RAG_PROVIDER", DEFAULT_PROVIDER))
    embedding = _embedding_snapshot()
    result: dict[str, Any] = {
        "status": "configured",
        "provider": provider,
        "provider_source": "knowledge_base" if kb_provider else "runtime",
        "kb_name": kb_name,
        "checks": [],
        **embedding,
    }

    if provider != DEFAULT_PROVIDER:
        result.update({
            "uri": "local",
            "message": "Using local LlamaIndex compatibility storage.",
        })
        result["checks"].append({
            "name": "provider",
            "status": "ok",
            "message": "Local compatibility provider selected.",
        })
        return _with_readiness(result)

    uri = _env_value("MILVUS_URI", default_milvus_uri()).strip() or default_milvus_uri()
    token = _env_value("MILVUS_TOKEN", "").strip() or None
    marker = _read_marker(kb_base_dir, kb_name)
    marker_error = marker.pop("_marker_error", None)
    collection_name = str(marker.get("collection_name") or "").strip()
    legacy_storage_present = _has_legacy_storage(kb_base_dir, kb_name)

    result.update({
        "uri": uri,
        "proxy": _proxy_snapshot(uri),
        "marker_present": bool(marker),
        "collection_name": collection_name or None,
        "marker": marker,
        "legacy_storage_present": legacy_storage_present,
        "needs_reindex": legacy_storage_present and not bool(marker),
    })
    marker_vector_count = _coerce_int(marker.get("vector_count"))
    if marker_vector_count is None:
        marker_vector_count = _coerce_int(marker.get("row_count"))
    if marker_vector_count is not None:
        result["vector_row_count"] = marker_vector_count

    if marker_error:
        result["status"] = "warning"
        result["checks"].append({
            "name": "marker",
            "status": "warning",
            "message": f"Milvus marker could not be read: {marker_error}",
        })
    elif kb_name and not marker and legacy_storage_present:
        result["status"] = "warning"
        result["checks"].append({
            "name": "legacy_storage",
            "status": "warning",
            "message": "Legacy LlamaIndex storage exists but Milvus metadata is missing. Rebuild this knowledge base.",
        })
    elif kb_name and not marker:
        result["status"] = "warning"
        result["checks"].append({
            "name": "marker",
            "status": "warning",
            "message": "No Milvus marker found. Rebuild the index after uploading raw files.",
        })
    else:
        result["checks"].append({
            "name": "marker",
            "status": "ok",
            "message": "Milvus metadata marker is available." if kb_name else "No KB-specific marker requested.",
        })

    if marker:
        schema_version = marker.get("schema_version")
        result["marker_schema_version"] = schema_version
        if schema_version is None:
            result["checks"].append({
                "name": "marker_schema",
                "status": "warning",
                "message": (
                    "Milvus marker uses the legacy metadata schema. It remains usable; "
                    "rebuild the index to refresh diagnostic metadata."
                ),
            })
        elif schema_version != MILVUS_MARKER_SCHEMA_VERSION:
            _set_warning(result)
            result["checks"].append({
                "name": "marker_schema",
                "status": "warning",
                "message": (
                    f"Milvus marker schema version {schema_version} differs from "
                    f"the supported version {MILVUS_MARKER_SCHEMA_VERSION}."
                ),
            })

        marker_uri = str(marker.get("uri") or "").strip()
        if marker_uri:
            result["indexed_uri"] = marker_uri
            result["uri_mismatch"] = marker_uri != uri
            if marker_uri != uri:
                hint = _milvus_uri_mismatch_hint(marker_uri, uri)
                result["uri_mismatch_kind"] = hint["kind"]
                result["uri_mismatch_summary"] = hint["summary"]
                result["uri_mismatch_action"] = hint["primary_action"]
                _set_warning(result)
                result["checks"].append({
                    "name": "milvus_uri",
                    "status": "warning",
                    "message": hint["summary"],
                })

        embedding_check = _marker_embedding_check(marker, embedding)
        result.update(embedding_check)
        if embedding_check["embedding_mismatch"]:
            result["needs_reindex"] = True
            _set_warning(result)
            result["checks"].append({
                "name": "embedding",
                "status": "warning",
                "message": (
                    "The knowledge base was indexed with a different embedding "
                    "model or dimension. Rebuild the index with the current embedding settings."
                ),
            })
        elif embedding_check["indexed_embedding_model"] or embedding_check["indexed_embedding_dim"] is not None:
            result["checks"].append({
                "name": "embedding",
                "status": "ok",
                "message": "Indexed embedding settings match the current runtime.",
            })

    if is_local_file_uri(uri):
        local_parent = Path(uri).expanduser().parent
        result["local_parent_exists"] = local_parent.exists()
        if platform.system().lower() == "windows":
            _set_warning(result)
            result["checks"].append({
                "name": "milvus_lite",
                "status": "warning",
                "message": "Milvus Lite file mode is not available on native Windows Python. Use Docker/Standalone or WSL.",
            })
            return _with_readiness(result)
        if not local_parent.exists():
            result["checks"].append({
                "name": "milvus_lite",
                "status": "warning",
                "message": f"Milvus Lite directory does not exist yet: {local_parent}",
            })

    if not check_connection:
        result["checks"].append({
            "name": "connection",
            "status": "skipped",
            "message": "Connection check skipped.",
        })
        return _with_readiness(result)

    if kb_name and not collection_name:
        result["checks"].append({
            "name": "connection",
            "status": "skipped",
            "message": "Milvus connection check skipped because this knowledge base has no collection metadata yet.",
        })
        return _with_readiness(result)

    if milvus_http.is_http_uri(uri):
        timeout = _env_float("RAG_DIAGNOSTICS_TIMEOUT_SECONDS", 3.0)
        result["connection_timeout_seconds"] = timeout
        proxy = result.get("proxy") if isinstance(result.get("proxy"), dict) else {}
        if proxy.get("http_proxy_configured") or proxy.get("https_proxy_configured"):
            result["checks"].append({
                "name": "proxy",
                "status": "ok" if proxy.get("milvus_proxy_bypassed") else "warning",
                "message": (
                    "Milvus 本地/内网地址会绕过 HTTP 代理。"
                    if proxy.get("milvus_proxy_bypassed")
                    else "当前 Milvus 地址会使用 HTTP 代理；如果是本地服务，请配置 NO_PROXY。"
                ),
            })
        try:
            if collection_name:
                milvus_http.describe_collection(uri, token, collection_name)
                row_count = milvus_http.collection_row_count(uri, token, collection_name)
                result["collection_present"] = True
                result["vector_row_count"] = row_count
                result["checks"].append({
                    "name": "collection",
                    "status": "ok",
                    "message": (
                        f"Collection '{collection_name}' exists"
                        + (f" with {row_count} row(s)." if row_count is not None else ".")
                    ),
                })
                if row_count == 0:
                    _set_warning(result)
                    result["checks"].append({
                        "name": "vector_rows",
                        "status": "warning",
                        "message": "Milvus collection exists but contains 0 rows. Rebuild the index.",
                    })
            else:
                collections = milvus_http.list_collections(uri, token)
                result["collection_count"] = len(collections)
                result["checks"].append({
                    "name": "connection",
                "status": "ok",
                "message": f"Connected to Milvus REST. {len(collections)} collection(s) visible.",
            })
            if result["status"] not in {"warning", "error"}:
                result["status"] = "ok"
        except Exception as exc:
            message = str(exc)
            error_kind = _connection_error_kind(message)
            result["status"] = "error"
            result["connection_error_kind"] = error_kind
            if error_kind == "connection_refused":
                result["milvus_service_running"] = False
            result["runtime_action"] = _runtime_action_for_error(
                error_kind,
                uri=uri,
                uri_mismatch=bool(result.get("uri_mismatch")),
            )
            result["checks"].append({
                "name": "connection",
                "status": "error",
                "message": message,
            })
        return _with_readiness(result)

    try:
        from pymilvus import MilvusClient
    except ImportError:
        result["status"] = "error"
        result["checks"].append({
            "name": "dependency",
            "status": "error",
            "message": "pymilvus is not installed. Install requirements/server.txt.",
        })
        return _with_readiness(result)

    timeout = _env_float("RAG_DIAGNOSTICS_TIMEOUT_SECONDS", 3.0)
    result["connection_timeout_seconds"] = timeout

    try:
        client = MilvusClient(uri=uri, token=token, timeout=timeout)
        if collection_name:
            collection_present = client.has_collection(collection_name, timeout=timeout)
            result["collection_present"] = collection_present
            result["checks"].append({
                "name": "collection",
                "status": "ok" if collection_present else "warning",
                "message": (
                    f"Collection '{collection_name}' exists."
                    if collection_present
                    else f"Collection '{collection_name}' was not found. Rebuild the index."
                ),
            })
            if not collection_present and result["status"] != "error":
                result["status"] = "warning"
        else:
            collections = client.list_collections(timeout=timeout)
            result["collection_count"] = len(collections)
            result["checks"].append({
                "name": "connection",
                "status": "ok",
                "message": f"Connected to Milvus. {len(collections)} collection(s) visible.",
            })
        if result["status"] not in {"warning", "error"}:
            result["status"] = "ok"
    except Exception as exc:
        message = str(exc)
        error_kind = _connection_error_kind(message)
        result["status"] = "error"
        result["connection_error_kind"] = error_kind
        if error_kind == "connection_refused":
            result["milvus_service_running"] = False
        result["runtime_action"] = _runtime_action_for_error(
            error_kind,
            uri=uri,
            uri_mismatch=bool(result.get("uri_mismatch")),
        )
        result["checks"].append({
            "name": "connection",
            "status": "error",
            "message": message,
        })

    return _with_readiness(result)


def preflight_rag_environment(
    *,
    kb_base_dir: str | Path,
    kb_name: str | None = None,
    check_connection: bool = True,
    check_docker: bool = True,
) -> dict[str, Any]:
    """Return an operator-focused preflight for the real RAG runtime."""
    diagnostic = diagnose_rag(
        kb_base_dir=kb_base_dir,
        kb_name=kb_name,
        check_connection=check_connection,
    )
    readiness = diagnostic.get("readiness") if isinstance(diagnostic.get("readiness"), dict) else {}
    docker = _docker_snapshot() if check_docker else {"skipped": True}
    commands = [
        "python scripts/start_docker.py --milvus-only",
    ]
    if kb_name:
        commands.append(f"sparkweave kb reindex {kb_name} --provider milvus")
    commands.append(
        "python scripts/rag_e2e_acceptance.py --base-url http://127.0.0.1:8001 --chat-check --cleanup"
    )
    return {
        "status": readiness.get("state") or diagnostic.get("status") or "unknown",
        "label": readiness.get("label") or "RAG 预检",
        "summary": readiness.get("summary") or "",
        "primary_action": readiness.get("primary_action") or "",
        "kb_name": kb_name,
        "diagnostic": diagnostic,
        "docker": docker,
        "recommended_commands": commands,
    }


__all__ = [
    "default_milvus_uri",
    "diagnose_rag",
    "is_local_file_uri",
    "preflight_rag_environment",
]
