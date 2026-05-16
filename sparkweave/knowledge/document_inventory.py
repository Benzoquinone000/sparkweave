"""Document-level management helpers for knowledge bases.

Raw files are the source of truth. Vector rows are derived data that can be
listed and deleted independently when Milvus is the active RAG backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
from typing import Any

from sparkweave.knowledge.manager import KnowledgeBaseManager
from sparkweave.services.rag_support.factory import DEFAULT_PROVIDER, normalize_provider_name
from sparkweave.services.rag_support.file_routing import FileTypeRouter
from sparkweave.services.rag_support import milvus_http

MAX_VECTOR_SCAN = 5000


@dataclass(frozen=True)
class RawDocumentRef:
    id: str
    path: Path
    relative_path: str


def document_id_for_path(path: Path, raw_dir: Path) -> str:
    """Return a stable public id for a raw document path."""
    try:
        relative = path.resolve().relative_to(raw_dir.resolve()).as_posix()
    except ValueError:
        relative = path.name
    return hashlib.sha1(relative.encode("utf-8")).hexdigest()[:16]


def list_documents(manager: KnowledgeBaseManager, kb_name: str, *, include_vectors: bool = True) -> dict[str, Any]:
    """List raw documents and, when possible, their vector-row counts."""
    kb_dir = manager.get_knowledge_base_path(kb_name)
    raw_dir = manager.get_raw_path(kb_name)
    vector_index, vector_meta = _vector_index_by_document(manager, kb_name) if include_vectors else ({}, {})
    vectors_available = bool(vector_meta.get("available")) if include_vectors else False
    documents: list[dict[str, Any]] = []

    for ref in _iter_raw_document_refs(raw_dir):
        stat = ref.path.stat()
        cache_path = _markdown_cache_path(kb_dir, ref)
        vector_info = _vector_info_for_document(vector_index, ref)
        vector_count = int(vector_info.get("vector_count") or 0) if vectors_available else None
        documents.append(
            {
                "id": ref.id,
                "name": ref.path.name,
                "extension": ref.path.suffix.lower(),
                "relative_path": ref.relative_path,
                "raw_path": str(ref.path),
                "size": stat.st_size,
                "size_human": _format_bytes(stat.st_size),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "content_available": _is_preview_supported(ref.path),
                "extracted_cached": cache_path.exists(),
                "vector_count": vector_count,
                "vectors_available": vectors_available,
                "sample_chunks": vector_info.get("sample_chunks") or [],
            }
        )

    documents.sort(key=lambda item: str(item["name"]).lower())
    return {
        "kb_name": kb_name,
        "documents": documents,
        "document_count": len(documents),
        "vector_count": sum(int(item.get("vector_count") or 0) for item in documents) if vectors_available else None,
        "vectors_available": vectors_available,
        "vector_error": vector_meta.get("error") or "",
        "provider": _kb_provider(manager, kb_name),
    }


def preview_document(
    manager: KnowledgeBaseManager,
    kb_name: str,
    document_id: str,
    *,
    max_chars: int = 24000,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Return a Markdown/text preview for one raw document.

    PDFs use the same extraction strategy as ingestion. The result is cached
    under ``extracted_markdown`` so users can inspect the OCR/text-layer output
    without repeatedly running heavy OCR.
    """
    kb_dir = manager.get_knowledge_base_path(kb_name)
    ref = resolve_document_ref(manager, kb_name, document_id)
    cache_path = _markdown_cache_path(kb_dir, ref)

    if cache_path.exists() and not force_refresh:
        content = cache_path.read_text(encoding="utf-8", errors="replace")
        generated = False
    else:
        content = _extract_preview_content(ref.path)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(content, encoding="utf-8")
        generated = True

    clipped = content[: max(0, max_chars)] if max_chars else content
    return {
        "kb_name": kb_name,
        "document": _document_payload(ref, kb_dir),
        "content": clipped,
        "content_chars": len(content),
        "truncated": len(clipped) < len(content),
        "cache_path": str(cache_path),
        "cached": cache_path.exists(),
        "generated": generated,
    }


def list_vector_chunks(
    manager: KnowledgeBaseManager,
    kb_name: str,
    *,
    document_id: str | None = None,
    limit: int = 80,
    offset: int = 0,
) -> dict[str, Any]:
    """List vector rows stored for a KB or one document."""
    limit = max(1, min(int(limit or 80), 200))
    offset = max(0, int(offset or 0))
    ref = resolve_document_ref(manager, kb_name, document_id) if document_id else None
    rows, meta = _query_milvus_rows(manager, kb_name, limit=MAX_VECTOR_SCAN if ref else limit, offset=0 if ref else offset)
    chunks = [_chunk_payload(row, meta) for row in rows]
    if ref:
        chunks = [chunk for chunk in chunks if _chunk_matches_document(chunk, ref)]
    total = len(chunks) if ref else int(meta.get("returned_count") or len(chunks))
    page = chunks[offset : offset + limit] if ref else chunks
    return {
        "kb_name": kb_name,
        "provider": _kb_provider(manager, kb_name),
        "document_id": document_id,
        "chunks": page,
        "total": total,
        "limit": limit,
        "offset": offset,
        "collection": meta.get("collection_name") or "",
        "available": bool(meta.get("available")),
        "error": meta.get("error") or "",
    }


def delete_document(
    manager: KnowledgeBaseManager,
    kb_name: str,
    document_id: str,
    *,
    remove_raw: bool = True,
    remove_vectors: bool = True,
) -> dict[str, Any]:
    """Delete one raw document and/or its vector rows."""
    kb_dir = manager.get_knowledge_base_path(kb_name)
    ref = resolve_document_ref(manager, kb_name, document_id)
    deleted_vectors = 0
    vector_error = ""
    if remove_vectors:
        deleted_vectors, vector_error = delete_vectors_for_document(manager, kb_name, ref)

    deleted_raw = False
    if remove_raw and ref.path.exists():
        ref.path.unlink()
        deleted_raw = True

    cache_path = _markdown_cache_path(kb_dir, ref)
    deleted_cache = False
    if cache_path.exists():
        cache_path.unlink()
        deleted_cache = True

    _update_marker_document_count(manager, kb_name)
    return {
        "kb_name": kb_name,
        "document_id": document_id,
        "document_name": ref.path.name,
        "deleted_raw": deleted_raw,
        "deleted_cache": deleted_cache,
        "deleted_vectors": deleted_vectors,
        "vector_error": vector_error,
        "needs_reindex": bool(vector_error and _kb_provider(manager, kb_name) != "milvus"),
    }


def delete_vector_chunk(manager: KnowledgeBaseManager, kb_name: str, node_id: str) -> dict[str, Any]:
    """Delete one vector row by primary id."""
    deleted, error = _delete_milvus_ids(manager, kb_name, [node_id])
    return {
        "kb_name": kb_name,
        "node_id": node_id,
        "deleted_vectors": deleted,
        "error": error,
    }


def delete_vectors_for_document(
    manager: KnowledgeBaseManager,
    kb_name: str,
    ref: RawDocumentRef,
) -> tuple[int, str]:
    rows, meta = _query_milvus_rows(manager, kb_name, limit=MAX_VECTOR_SCAN, offset=0)
    if not meta.get("available"):
        return 0, str(meta.get("error") or "Milvus vector rows are not available")
    ids = [
        str(chunk["id"])
        for chunk in (_chunk_payload(row, meta) for row in rows)
        if chunk.get("id") and _chunk_matches_document(chunk, ref)
    ]
    return _delete_milvus_ids(manager, kb_name, ids)


def resolve_document_ref(manager: KnowledgeBaseManager, kb_name: str, document_id: str | None) -> RawDocumentRef:
    if not document_id:
        raise ValueError("Document id is required")
    raw_dir = manager.get_raw_path(kb_name)
    for ref in _iter_raw_document_refs(raw_dir):
        if ref.id == document_id:
            return ref
    raise ValueError(f"Document not found: {document_id}")


def _iter_raw_document_refs(raw_dir: Path) -> list[RawDocumentRef]:
    if not raw_dir.exists():
        return []
    refs: list[RawDocumentRef] = []
    for path in raw_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            relative = path.resolve().relative_to(raw_dir.resolve()).as_posix()
        except ValueError:
            relative = path.name
        refs.append(RawDocumentRef(id=document_id_for_path(path, raw_dir), path=path, relative_path=relative))
    return refs


def _document_payload(ref: RawDocumentRef, kb_dir: Path) -> dict[str, Any]:
    stat = ref.path.stat()
    cache_path = _markdown_cache_path(kb_dir, ref)
    return {
        "id": ref.id,
        "name": ref.path.name,
        "extension": ref.path.suffix.lower(),
        "relative_path": ref.relative_path,
        "raw_path": str(ref.path),
        "size": stat.st_size,
        "size_human": _format_bytes(stat.st_size),
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "content_available": _is_preview_supported(ref.path),
        "extracted_cached": cache_path.exists(),
    }


def _markdown_cache_path(kb_dir: Path, ref: RawDocumentRef) -> Path:
    safe_name = f"{ref.id}_{ref.path.stem}.md"
    return kb_dir / "extracted_markdown" / safe_name


def _is_preview_supported(path: Path) -> bool:
    return path.suffix.lower() in {".pdf"} | set(FileTypeRouter.TEXT_EXTENSIONS) | set(FileTypeRouter.IMAGE_EXTENSIONS)


def _extract_preview_content(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from sparkweave.services.rag_support.pipelines.llamaindex import LlamaIndexPipeline

        pipeline = LlamaIndexPipeline()
        text = pipeline._extract_pdf_text(path)
    elif suffix in set(FileTypeRouter.IMAGE_EXTENSIONS):
        from sparkweave.services.rag_support.pipelines.llamaindex import LlamaIndexPipeline

        pipeline = LlamaIndexPipeline()
        text = pipeline._extract_image_text(path)
    elif suffix in set(FileTypeRouter.TEXT_EXTENSIONS):
        text = path.read_text(encoding="utf-8", errors="replace")
    else:
        text = ""
    title = f"# {path.name}\n\n"
    return title + (text.strip() or "当前文件没有可预览文本。")


def _kb_provider(manager: KnowledgeBaseManager, kb_name: str) -> str:
    try:
        info = manager.get_info(kb_name)
        metadata = info.get("metadata") if isinstance(info.get("metadata"), dict) else {}
        return normalize_provider_name(str(metadata.get("rag_provider") or DEFAULT_PROVIDER))
    except Exception:
        return normalize_provider_name(DEFAULT_PROVIDER)


def _vector_index_by_document(manager: KnowledgeBaseManager, kb_name: str) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    rows, meta = _query_milvus_rows(manager, kb_name, limit=MAX_VECTOR_SCAN, offset=0)
    if not meta.get("available"):
        return {}, meta
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        chunk = _chunk_payload(row, meta)
        keys = _document_match_keys_from_chunk(chunk)
        if not keys:
            continue
        node_key = str(chunk.get("id") or chunk.get("node_id") or chunk.get("text_preview") or "")
        for key in keys:
            item = grouped.setdefault(key, {"vector_count": 0, "sample_chunks": [], "_seen": set()})
            seen = item.setdefault("_seen", set())
            if node_key and node_key in seen:
                continue
            if node_key:
                seen.add(node_key)
            item["vector_count"] += 1
            if len(item["sample_chunks"]) < 2:
                item["sample_chunks"].append(
                    {
                        "id": chunk.get("id"),
                        "text_preview": chunk.get("text_preview"),
                        "score": chunk.get("score"),
                    }
                )
    for item in grouped.values():
        item.pop("_seen", None)
    return grouped, meta


def _vector_info_for_document(
    vector_index: dict[str, dict[str, Any]],
    ref: RawDocumentRef,
) -> dict[str, Any]:
    for key in _document_match_keys_for_ref(ref):
        info = vector_index.get(key)
        if info:
            return info
    return {}


def _query_milvus_rows(
    manager: KnowledgeBaseManager,
    kb_name: str,
    *,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    marker = _read_milvus_marker(manager, kb_name)
    collection_name = str(marker.get("collection_name") or "")
    if not collection_name:
        return [], {"available": False, "error": "No Milvus collection marker", "collection_name": ""}
    uri = _milvus_uri()
    token = _milvus_token()

    if _prefer_rest_milvus_client(uri):
        return _query_milvus_rows_via_rest(uri, token, collection_name, limit=limit, offset=offset)

    try:
        from pymilvus import MilvusClient
    except ImportError:
        if milvus_http.is_http_uri(uri):
            return _query_milvus_rows_via_rest(uri, token, collection_name, limit=limit, offset=offset)
        return [], {"available": False, "error": "pymilvus is not installed", "collection_name": collection_name}

    try:
        client = MilvusClient(uri=uri, token=token)
        if not client.has_collection(collection_name):
            return [], {"available": False, "error": "Milvus collection does not exist", "collection_name": collection_name}
    except Exception as exc:
        if milvus_http.is_http_uri(uri):
            return _query_milvus_rows_via_rest(uri, token, collection_name, limit=limit, offset=offset)
        return [], {"available": False, "error": str(exc), "collection_name": collection_name}

    primary_field = _primary_field(client, collection_name)
    output_fields = _query_output_fields(client, collection_name)
    try:
        rows = client.query(
            collection_name=collection_name,
            filter="",
            output_fields=output_fields,
            limit=max(1, min(limit, MAX_VECTOR_SCAN)),
            offset=max(0, offset),
        )
    except TypeError:
        rows = client.query(
            collection_name,
            "",
            output_fields=output_fields,
            limit=max(1, min(limit, MAX_VECTOR_SCAN)),
            offset=max(0, offset),
        )
    except Exception:
        rows = client.query(
            collection_name=collection_name,
            filter="",
            output_fields=["*"],
            limit=max(1, min(limit, MAX_VECTOR_SCAN)),
            offset=max(0, offset),
        )
    return list(rows or []), {
        "available": True,
        "collection_name": collection_name,
        "primary_field": primary_field,
        "returned_count": len(rows or []),
    }


def _delete_milvus_ids(manager: KnowledgeBaseManager, kb_name: str, ids: list[str]) -> tuple[int, str]:
    clean_ids = [item for item in dict.fromkeys(str(item) for item in ids if item)]
    if not clean_ids:
        return 0, ""
    marker = _read_milvus_marker(manager, kb_name)
    collection_name = str(marker.get("collection_name") or "")
    if not collection_name:
        return 0, "No Milvus collection marker"
    uri = _milvus_uri()
    token = _milvus_token()
    if _prefer_rest_milvus_client(uri):
        return _delete_milvus_ids_via_rest(uri, token, collection_name, clean_ids)
    try:
        from pymilvus import MilvusClient
    except ImportError:
        if milvus_http.is_http_uri(uri):
            return _delete_milvus_ids_via_rest(uri, token, collection_name, clean_ids)
        return 0, "pymilvus is not installed"
    try:
        client = MilvusClient(uri=uri, token=token)
        if not client.has_collection(collection_name):
            return 0, "Milvus collection does not exist"
        try:
            client.delete(collection_name=collection_name, ids=clean_ids)
        except TypeError:
            primary = _primary_field(client, collection_name)
            quoted = ", ".join(json.dumps(item, ensure_ascii=False) for item in clean_ids)
            client.delete(collection_name=collection_name, filter=f"{primary} in [{quoted}]")
        return len(clean_ids), ""
    except Exception as exc:
        if milvus_http.is_http_uri(uri):
            return _delete_milvus_ids_via_rest(uri, token, collection_name, clean_ids)
        return 0, str(exc)


def _read_milvus_marker(manager: KnowledgeBaseManager, kb_name: str) -> dict[str, Any]:
    marker = manager.get_knowledge_base_path(kb_name) / "milvus_storage" / "metadata.json"
    if not marker.exists():
        return {}
    try:
        return json.loads(marker.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _env_value(name: str, default: str = "") -> str:
    try:
        from sparkweave.services.config import get_env_store

        return get_env_store().get(name, default)
    except Exception:
        return os.getenv(name, default)


def _default_milvus_uri() -> str:
    if platform.system().lower() == "windows":
        return "http://localhost:19530"
    return "./data/milvus/sparkweave.db"


def _milvus_uri() -> str:
    return _env_value("MILVUS_URI", _default_milvus_uri()).strip() or _default_milvus_uri()


def _milvus_token() -> str | None:
    return _env_value("MILVUS_TOKEN", "").strip() or None


def _prefer_rest_milvus_client(uri: str) -> bool:
    preferred = _env_value("SPARKWEAVE_MILVUS_INSPECTION_CLIENT", "").strip().lower()
    if preferred in {"rest", "http", "restful"}:
        return milvus_http.is_http_uri(uri)
    if preferred in {"pymilvus", "native"}:
        return False
    return milvus_http.is_http_uri(uri)


def _query_milvus_rows_via_rest(
    uri: str,
    token: str | None,
    collection_name: str,
    *,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        description = milvus_http.describe_collection(uri, token, collection_name)
        primary_field = milvus_http.primary_field(description)
        output_fields = milvus_http.query_output_fields(description)
        try:
            row_count = milvus_http.collection_row_count(uri, token, collection_name)
        except Exception:
            row_count = None
        rows = milvus_http.query_entities(
            uri,
            token,
            collection_name,
            output_fields=output_fields,
            limit=max(1, min(limit, MAX_VECTOR_SCAN)),
            offset=max(0, offset),
        )
        return list(rows or []), {
            "available": True,
            "collection_name": collection_name,
            "primary_field": primary_field,
            "returned_count": len(rows or []),
            "collection_row_count": row_count,
            "inspection_client": "rest",
        }
    except Exception as exc:
        return [], {
            "available": False,
            "error": str(exc),
            "collection_name": collection_name,
            "inspection_client": "rest",
        }


def _delete_milvus_ids_via_rest(
    uri: str,
    token: str | None,
    collection_name: str,
    ids: list[str],
) -> tuple[int, str]:
    try:
        description = milvus_http.describe_collection(uri, token, collection_name)
        primary = milvus_http.primary_field(description)
        quoted = ", ".join(json.dumps(item, ensure_ascii=False) for item in ids)
        milvus_http.delete_entities(
            uri,
            token,
            collection_name,
            filter_expr=f"{primary} in [{quoted}]",
        )
        return len(ids), ""
    except Exception as exc:
        return 0, str(exc)


def _update_marker_document_count(manager: KnowledgeBaseManager, kb_name: str) -> None:
    marker_path = manager.get_knowledge_base_path(kb_name) / "milvus_storage" / "metadata.json"
    if not marker_path.exists():
        return
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        marker["document_count"] = len(_iter_raw_document_refs(manager.get_raw_path(kb_name)))
        marker["updated_at"] = datetime.now().isoformat()
        marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        return


def _primary_field(client: Any, collection_name: str) -> str:
    try:
        desc = client.describe_collection(collection_name)
        fields = (desc.get("schema") or {}).get("fields") or desc.get("fields") or []
        for field in fields:
            if field.get("is_primary"):
                return str(field.get("name") or "id")
    except Exception:
        pass
    return "id"


def _query_output_fields(client: Any, collection_name: str) -> list[str]:
    try:
        desc = client.describe_collection(collection_name)
        fields = (desc.get("schema") or {}).get("fields") or desc.get("fields") or []
        names = [str(field.get("name")) for field in fields if field.get("name")]
        excluded = {"embedding", "vector", "sparse_embedding"}
        return [name for name in names if name not in excluded] or ["*"]
    except Exception:
        return ["*"]


def _chunk_payload(row: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    metadata = _extract_metadata(row)
    node_content = _json_obj(row.get("_node_content"))
    relationship_metadata, relationship_doc_ids = _extract_relationship_metadata(node_content)
    for key, value in relationship_metadata.items():
        metadata.setdefault(key, value)
    text = str(
        row.get("text")
        or row.get("content")
        or node_content.get("text")
        or node_content.get("content")
        or ""
    )
    primary = str(meta.get("primary_field") or "id")
    node_id = str(row.get(primary) or row.get("id") or row.get("node_id") or node_content.get("id_") or "")
    document_id = _first_non_empty(
        metadata.get("document_id"),
        metadata.get("doc_id"),
        metadata.get("ref_doc_id"),
        row.get("document_id"),
        row.get("doc_id"),
        row.get("ref_doc_id"),
        node_content.get("ref_doc_id"),
        *relationship_doc_ids,
    )
    file_name = _first_non_empty(
        metadata.get("file_name"),
        metadata.get("filename"),
        metadata.get("title"),
        row.get("file_name"),
        row.get("filename"),
        row.get("title"),
    )
    file_path = _first_non_empty(
        metadata.get("file_path"),
        metadata.get("path"),
        metadata.get("source"),
        row.get("file_path"),
        row.get("path"),
        row.get("source"),
    )
    return {
        "id": node_id,
        "node_id": node_id,
        "file_name": file_name,
        "file_path": file_path,
        "document_id": document_id,
        "doc_id": document_id,
        "ref_doc_id": document_id,
        "relationship_doc_ids": relationship_doc_ids,
        "document_key": _document_match_key_from_values(file_name, file_path) or document_id,
        "text_preview": _compact_text(text, 360),
        "text_chars": len(text),
        "metadata": metadata,
        "score": row.get("score", ""),
    }


def _extract_metadata(row: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ("metadata", "_metadata"):
        raw = row.get(key)
        parsed = _json_obj(raw)
        if parsed:
            metadata.update(parsed)
    node_content = _json_obj(row.get("_node_content"))
    node_meta = node_content.get("metadata")
    if isinstance(node_meta, dict):
        metadata.update(node_meta)
    for key in (
        "file_name",
        "filename",
        "file_path",
        "path",
        "source",
        "relative_path",
        "page_label",
        "page",
        "title",
        "document_id",
        "doc_id",
        "ref_doc_id",
    ):
        if key in row and row[key] not in (None, ""):
            metadata.setdefault(key, row[key])
    return metadata


def _extract_relationship_metadata(node_content: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    relationships = node_content.get("relationships")
    if not isinstance(relationships, dict):
        return {}, []
    metadata: dict[str, Any] = {}
    doc_ids: list[str] = []
    for relationship in relationships.values():
        if not isinstance(relationship, dict):
            continue
        node_id = str(relationship.get("node_id") or "").strip()
        if node_id:
            doc_ids.append(node_id)
        rel_metadata = relationship.get("metadata")
        if isinstance(rel_metadata, dict):
            for key, value in rel_metadata.items():
                if value not in (None, ""):
                    metadata.setdefault(str(key), value)
    return metadata, doc_ids


def _json_obj(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _chunk_matches_document(chunk: dict[str, Any], document: RawDocumentRef | Path) -> bool:
    if isinstance(document, RawDocumentRef):
        ref = document
        raw_path = document.path
    else:
        raw_path = document
        ref = RawDocumentRef(
            id=document_id_for_path(raw_path, raw_path.parent),
            path=raw_path,
            relative_path=raw_path.name,
        )
    ref_keys = _document_match_keys_for_ref(ref)
    chunk_keys = _document_match_keys_from_chunk(chunk)
    if ref_keys & chunk_keys:
        return True
    file_name = str(chunk.get("file_name") or "")
    file_path = str(chunk.get("file_path") or "")
    return file_name == raw_path.name or file_path.replace("\\", "/").endswith(raw_path.name)


def _document_match_keys_for_ref(ref: RawDocumentRef) -> set[str]:
    keys = {
        ref.id,
        _normalize_doc_key(ref.relative_path),
        _normalize_doc_key(ref.path.name),
        _normalize_path_key(ref.relative_path),
        _normalize_path_key(str(ref.path)),
    }
    return {key for key in keys if key}


def _document_match_key(path: Path) -> str:
    return _normalize_doc_key(path.name)


def _document_match_keys_from_chunk(chunk: dict[str, Any]) -> set[str]:
    metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
    relationship_doc_ids = chunk.get("relationship_doc_ids")
    if not isinstance(relationship_doc_ids, list):
        relationship_doc_ids = []
    keys = {
        str(chunk.get("document_id") or "").strip(),
        str(chunk.get("doc_id") or "").strip(),
        str(chunk.get("ref_doc_id") or "").strip(),
        str(metadata.get("document_id") or "").strip(),
        str(metadata.get("doc_id") or "").strip(),
        str(metadata.get("ref_doc_id") or "").strip(),
        str(chunk.get("document_key") or "").strip(),
        _document_match_key_from_values(str(chunk.get("file_name") or ""), str(chunk.get("file_path") or "")),
        _document_match_key_from_values(str(metadata.get("file_name") or ""), str(metadata.get("file_path") or "")),
        _normalize_path_key(str(chunk.get("file_path") or "")),
        _normalize_path_key(str(metadata.get("file_path") or "")),
        _normalize_path_key(str(metadata.get("relative_path") or "")),
    }
    keys.update(str(item or "").strip() for item in relationship_doc_ids)
    return {key for key in keys if key}


def _document_match_key_from_values(file_name: str, file_path: str) -> str:
    return _normalize_doc_key(file_name or Path(file_path).name)


def _normalize_doc_key(value: str) -> str:
    return value.strip().replace("\\", "/").split("/")[-1].lower()


def _normalize_path_key(value: str) -> str:
    return value.strip().replace("\\", "/").lower()


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _compact_text(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def _format_bytes(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


__all__ = [
    "delete_document",
    "delete_vector_chunk",
    "document_id_for_path",
    "list_documents",
    "list_vector_chunks",
    "preview_document",
    "resolve_document_ref",
]
