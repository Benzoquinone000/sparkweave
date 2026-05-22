"""Milvus-backed RAG pipeline.

This pipeline keeps SparkWeave's existing ingestion behavior while moving the
vector store from local LlamaIndex JSON files to a real Milvus collection.
Local knowledge-base folders still hold raw files and a small metadata marker;
the searchable vectors live in Milvus.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import platform
import re
import time
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sparkweave.services.embedding_support import get_embedding_client, get_embedding_config
from sparkweave.services.rag_support import milvus_http
from sparkweave.services.rag_support.context_pack import build_context_pack
from sparkweave.services.rag_support.file_routing import DocumentType, FileTypeRouter
from sparkweave.services.rag_support.rerank import RerankConfig, normalize_reranker, rerank_nodes

MILVUS_MARKER_SCHEMA_VERSION = 1
DEFAULT_KB_BASE_DIR = str(
    Path(__file__).resolve().parent.parent.parent.parent.parent / "data" / "knowledge_bases"
)


def _env(name: str, default: str = "") -> str:
    try:
        from sparkweave.services.config import get_env_store

        return get_env_store().get(name, default)
    except Exception:
        return os.getenv(name, default)


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = _env(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _env_float(name: str) -> float | None:
    raw = _env(name, "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _env_float_default(name: str, default: float) -> float:
    value = _env_float(name)
    return default if value is None else value


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _coerce_optional_float(value: Any, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _stats_row_count(stats: Any) -> int | None:
    if not isinstance(stats, dict):
        return None
    for key in ("row_count", "rowCount", "num_entities"):
        try:
            return int(stats[key])
        except (KeyError, TypeError, ValueError):
            continue
    return None


def _normalize_retrieval_mode(value: Any, default: str = "dense") -> str:
    raw = str(value or "").strip().lower().replace("-", "_")
    if raw in {"hybrid", "dense_sparse", "sparse_dense", "bm25", "sparse"}:
        return "hybrid"
    if raw in {"dense", "vector", "semantic", "naive"}:
        return "dense"
    if raw in {"default", ""}:
        return default
    return default


def _resolve_retrieval_mode(value: Any = None, default: str = "dense") -> str:
    env_default = _normalize_retrieval_mode(_env("RAG_RETRIEVAL_MODE", ""), default)
    return _normalize_retrieval_mode(value, env_default)


def _normalize_hybrid_ranker(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("_", "").replace("-", "")
    if raw in {"weighted", "weightedranker", "weight"}:
        return "WeightedRanker"
    return "RRFRanker"


@dataclass(frozen=True)
class _LoadedDocument:
    text: str
    metadata: dict[str, Any]
    document_id: str


@dataclass(frozen=True)
class _TextChunk:
    node_id: str
    text: str
    metadata: dict[str, Any]
    document_id: str
    chunk_index: int


@dataclass(frozen=True)
class _TextSegment:
    text: str
    metadata: dict[str, Any]


class MilvusPipeline:
    """Milvus RAG pipeline.

    Indexing still uses LlamaIndex's document loaders and Milvus vector-store
    adapter when that optional runtime is healthy. Query-time retrieval uses
    Milvus REST directly for HTTP deployments, so a broken local LlamaIndex
    install cannot prevent an already-indexed Milvus knowledge base from being
    searched.
    """

    provider = "milvus"

    def __init__(self, kb_base_dir: Optional[str] = None):
        self.logger = logging.getLogger("sparkweave.rag.milvus")
        self.kb_base_dir = kb_base_dir or DEFAULT_KB_BASE_DIR
        self._configure_settings()

    def _configure_settings(self) -> None:
        """Record embedding/chunk settings without importing LlamaIndex."""
        embedding_cfg = get_embedding_config()
        self.chunk_size = _env_int("RAG_CHUNK_SIZE", 512)
        self.chunk_overlap = _env_int("RAG_CHUNK_OVERLAP", 50)

        binding = getattr(embedding_cfg, "binding", "")
        self.logger.info(
            "Milvus RAG configured: embedding=%s (%sD, %s), chunk_size=%s",
            embedding_cfg.model,
            embedding_cfg.dim,
            binding,
            self.chunk_size,
        )

    @staticmethod
    def _llamaindex_runtime():
        try:
            from llama_index.core import Settings, StorageContext, VectorStoreIndex

            from sparkweave.services.rag_support.pipelines.llamaindex import (
                CustomEmbedding,
                LlamaIndexPipeline,
            )
        except Exception as exc:
            raise ImportError(
                "LlamaIndex runtime is unavailable. Existing HTTP Milvus "
                "collections can still be searched, but indexing and local "
                "Milvus-Lite retrieval require a healthy LlamaIndex install."
            ) from exc
        return Settings, StorageContext, VectorStoreIndex, CustomEmbedding, LlamaIndexPipeline

    def _configure_llamaindex_runtime(self):
        Settings, StorageContext, VectorStoreIndex, CustomEmbedding, LlamaIndexPipeline = (
            self._llamaindex_runtime()
        )
        Settings.embed_model = CustomEmbedding()
        Settings.chunk_size = self.chunk_size
        Settings.chunk_overlap = self.chunk_overlap
        return Settings, StorageContext, VectorStoreIndex, CustomEmbedding, LlamaIndexPipeline

    async def _verify_embedding_connectivity(self) -> None:
        self.logger.info("Verifying embedding API connectivity...")
        try:
            client = get_embedding_client()
            result = await client.embed(["connectivity test"])
            if not result or not result[0]:
                raise RuntimeError("Embedding API returned empty result")
            embedding_cfg = get_embedding_config()
            actual_dim = len(result[0])
            if embedding_cfg.dim and actual_dim != embedding_cfg.dim:
                raise RuntimeError(
                    "Embedding dimension mismatch: "
                    f"configured EMBEDDING_DIMENSION={embedding_cfg.dim}, "
                    f"API returned {actual_dim}. "
                    "Update the embedding dimension setting and rebuild the knowledge base."
                )
            self.logger.info("Embedding API OK (returned %s-dim vector)", actual_dim)
        except Exception as exc:
            self.logger.error("Embedding API connectivity check failed: %s", exc)
            raise RuntimeError(
                f"Cannot reach embedding API. Please check your embedding configuration. Error: {exc}"
            ) from exc

    async def _load_documents(self, file_paths: List[str]) -> list[Any]:
        *_, LlamaIndexPipeline = self._llamaindex_runtime()
        helper = LlamaIndexPipeline.__new__(LlamaIndexPipeline)
        helper.logger = self.logger
        helper.kb_base_dir = self.kb_base_dir
        return await helper._load_documents(file_paths)

    @staticmethod
    def _relative_path_for_file(file_path: Path) -> str:
        try:
            resolved = file_path.resolve()
            parts = resolved.parts
            raw_index = len(parts) - 1 - parts[::-1].index("raw")
            if raw_index < len(parts) - 1:
                return Path(*parts[raw_index + 1 :]).as_posix()
        except (OSError, ValueError):
            pass
        return file_path.name

    @classmethod
    def _document_id_for_file(cls, file_path: Path) -> str:
        relative_path = cls._relative_path_for_file(file_path)
        return hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def _document_metadata(
        cls,
        file_path: Path,
        *,
        source_type: str = "",
    ) -> dict[str, Any]:
        document_id = cls._document_id_for_file(file_path)
        metadata: dict[str, Any] = {
            "file_name": file_path.name,
            "file_path": str(file_path),
            "relative_path": cls._relative_path_for_file(file_path),
            "document_id": document_id,
            "doc_id": document_id,
            "ref_doc_id": document_id,
        }
        if source_type:
            metadata["source_type"] = source_type
        return metadata

    async def _load_http_documents(self, file_paths: list[str]) -> list[_LoadedDocument]:
        """Load documents for REST ingestion without importing LlamaIndex."""
        documents: list[_LoadedDocument] = []
        classification = FileTypeRouter.classify_files(file_paths)

        for file_path_str in classification.parser_files:
            file_path = Path(file_path_str)
            doc_type = FileTypeRouter.get_document_type(str(file_path))
            if doc_type == DocumentType.IMAGE:
                self.logger.info("Parsing image with OCR: %s", file_path.name)
                text = self._extract_image_text(file_path)
                source_type = "image_ocr"
            elif doc_type == DocumentType.DOCX:
                self.logger.info("Parsing DOCX: %s", file_path.name)
                text = self._extract_docx_text(file_path)
                source_type = "docx"
            else:
                self.logger.info("Parsing PDF: %s", file_path.name)
                text = self._extract_pdf_text(file_path)
                source_type = "pdf"
            if text.strip():
                metadata = self._document_metadata(file_path, source_type=source_type)
                documents.append(
                    _LoadedDocument(
                        text=text,
                        metadata=metadata,
                        document_id=str(metadata["document_id"]),
                    )
                )
                self.logger.info("Loaded: %s (%s chars)", file_path.name, len(text))
            else:
                self.logger.warning("Skipped empty document: %s", file_path.name)

        for file_path_str in classification.text_files:
            file_path = Path(file_path_str)
            self.logger.info("Parsing text: %s", file_path.name)
            text = await FileTypeRouter.read_text_file(str(file_path))
            if text.strip():
                metadata = self._document_metadata(file_path)
                documents.append(
                    _LoadedDocument(
                        text=text,
                        metadata=metadata,
                        document_id=str(metadata["document_id"]),
                    )
                )
                self.logger.info("Loaded: %s (%s chars)", file_path.name, len(text))
            else:
                self.logger.warning("Skipped empty document: %s", file_path.name)

        for file_path_str in classification.unsupported:
            self.logger.warning("Skipped unsupported file: %s", Path(file_path_str).name)

        return documents

    def _extract_pdf_text(self, file_path: Path) -> str:
        strategy = _env("SPARKWEAVE_PDF_OCR_STRATEGY", "auto").strip().lower()
        if strategy in {"iflytek_first", "ocr_first", "iflytek", "siliconflow_first", "deepseekocr_first"}:
            try:
                from sparkweave.services.ocr import ocr_pdf

                text = ocr_pdf(file_path)
                if text.strip():
                    self.logger.info("Extracted PDF text with OCR provider: %s", file_path.name)
                    return text
                self.logger.warning("OCR returned empty text for %s; falling back to PyMuPDF", file_path.name)
            except Exception as exc:
                self.logger.warning("OCR unavailable for %s; falling back to PyMuPDF: %s", file_path.name, exc)
            return self._extract_pdf_text_default(file_path)

        text = self._extract_pdf_text_default(file_path)
        min_chars = _env_int("SPARKWEAVE_OCR_MIN_TEXT_CHARS", 40)
        if len(text.strip()) >= min_chars:
            return text
        try:
            from sparkweave.services.ocr import is_ocr_configured, ocr_pdf

            if not is_ocr_configured():
                return text
            ocr_text = ocr_pdf(file_path)
            if ocr_text.strip():
                self.logger.info("Used OCR fallback for scanned PDF: %s", file_path.name)
                return ocr_text
        except Exception as exc:
            self.logger.warning("OCR fallback failed for %s: %s", file_path.name, exc)
        return text

    def _extract_pdf_text_default(self, file_path: Path) -> str:
        try:
            import fitz

            doc = fitz.open(file_path)
            texts = []
            for index, page in enumerate(doc, start=1):
                page_text = str(page.get_text() or "").strip()
                if page_text:
                    texts.append(f"[[sparkweave-page:{index}]]\n{page_text}")
            doc.close()
            return "\n\n".join(texts)
        except ImportError:
            self.logger.warning("PyMuPDF is not installed. Cannot extract PDF text.")
            return ""
        except Exception as exc:
            self.logger.error("Failed to extract PDF text: %s", exc)
            return ""

    def _extract_docx_text(self, file_path: Path) -> str:
        """Extract paragraphs from a DOCX file using only the standard library."""
        try:
            import xml.etree.ElementTree as ET
            import zipfile

            with zipfile.ZipFile(file_path) as archive:
                xml_bytes = archive.read("word/document.xml")
            root = ET.fromstring(xml_bytes)
        except KeyError:
            self.logger.warning("DOCX file has no word/document.xml: %s", file_path.name)
            return ""
        except Exception as exc:
            self.logger.warning("Failed to extract DOCX text from %s: %s", file_path.name, exc)
            return ""

        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs: list[str] = []
        for paragraph in root.findall(".//w:p", ns):
            parts: list[str] = []
            for child in paragraph.iter():
                tag = child.tag.rsplit("}", 1)[-1]
                if tag == "t" and child.text:
                    parts.append(child.text)
                elif tag == "tab":
                    parts.append("\t")
                elif tag in {"br", "cr"}:
                    parts.append("\n")
            text = "".join(parts).strip()
            if text:
                paragraphs.append(text)
        return "\n\n".join(paragraphs)

    def _extract_image_text(self, file_path: Path) -> str:
        try:
            from sparkweave.services.ocr import is_ocr_configured, recognize_image

            if not is_ocr_configured():
                self.logger.warning("OCR is not configured. Cannot parse image: %s", file_path.name)
                return ""
            encoding = file_path.suffix.lower().lstrip(".") or "png"
            if encoding == "jpg":
                encoding = "jpeg"
            text = recognize_image(file_path.read_bytes(), encoding=encoding)
            if text.strip():
                self.logger.info("Extracted image text with OCR provider: %s", file_path.name)
            else:
                self.logger.warning("OCR returned empty text for image: %s", file_path.name)
            return text
        except Exception as exc:
            self.logger.warning("Failed to OCR image %s: %s", file_path.name, exc)
            return ""

    def _split_http_documents(self, documents: list[_LoadedDocument]) -> list[_TextChunk]:
        chunks: list[_TextChunk] = []
        chunk_size = max(1, int(getattr(self, "chunk_size", _env_int("RAG_CHUNK_SIZE", 512))))
        overlap = max(0, min(int(getattr(self, "chunk_overlap", _env_int("RAG_CHUNK_OVERLAP", 50))), chunk_size - 1))

        for document in documents:
            text = document.text.replace("\r\n", "\n").replace("\r", "\n")
            chunk_index = 0
            for segment in self._structured_segments(text):
                segment_metadata = {**document.metadata, **segment.metadata}
                for chunk_text in self._split_segment_text(
                    segment.text,
                    chunk_size=chunk_size,
                    overlap=overlap,
                ):
                    if chunk_text:
                        node_id = f"{document.document_id}-{chunk_index:04d}-{uuid4().hex[:8]}"
                        metadata = dict(segment_metadata)
                        metadata["chunk_index"] = chunk_index
                        chunks.append(
                            _TextChunk(
                                node_id=node_id,
                                text=chunk_text,
                                metadata=metadata,
                                document_id=document.document_id,
                                chunk_index=chunk_index,
                            )
                        )
                        chunk_index += 1
        return chunks

    @staticmethod
    def _page_marker(line: str) -> str | None:
        match = re.match(r"^\[\[sparkweave-page:(\d+)\]\]\s*$", line.strip())
        return match.group(1) if match else None

    @staticmethod
    def _heading_title(line: str) -> str | None:
        text = line.strip()
        if not text:
            return None
        patterns = [
            r"^#{1,6}\s+(.+)$",
            r"^(?:chapter|section)\s+\d+(?:\.\d+)*\b.*$",
            r"^第[一二三四五六七八九十百千万\d]+[章节讲]\s*.*$",
            r"^\d+(?:\.\d+){0,4}[\.、]?\s+(.+)$",
        ]
        for pattern in patterns:
            match = re.match(pattern, text, flags=re.IGNORECASE)
            if match:
                return (match.group(1) if match.groups() else text).strip()
        return None

    def _structured_segments(self, text: str) -> list[_TextSegment]:
        if _env("RAG_CHUNK_STRATEGY", "structure").strip().lower() in {"char", "character", "plain"}:
            return [_TextSegment(text=text, metadata={})] if text.strip() else []

        segments: list[_TextSegment] = []
        buffer: list[str] = []
        current_page = ""
        current_heading = ""

        def flush() -> None:
            nonlocal buffer
            segment_text = "\n".join(buffer).strip()
            if segment_text:
                metadata: dict[str, Any] = {}
                if current_page:
                    metadata["page_label"] = current_page
                    metadata["page"] = current_page
                if current_heading:
                    metadata["section_title"] = current_heading
                segments.append(_TextSegment(text=segment_text, metadata=metadata))
            buffer = []

        for raw_line in text.split("\n"):
            page = self._page_marker(raw_line)
            if page is not None:
                flush()
                current_page = page
                continue

            heading = self._heading_title(raw_line)
            if heading is not None:
                flush()
                current_heading = heading
                buffer.append(raw_line.strip())
                continue

            buffer.append(raw_line)
        flush()
        return segments or ([_TextSegment(text=text, metadata={})] if text.strip() else [])

    @staticmethod
    def _split_segment_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
        cleaned = str(text or "").strip()
        if not cleaned:
            return []

        splits = MilvusPipeline._recursive_text_splits(
            cleaned,
            chunk_size=chunk_size,
            separators=(
                "\n\n",
                "\n",
                "。",
                "！",
                "？",
                "；",
                ";",
                ".",
                "!",
                "?",
                "，",
                ",",
                "、",
                " ",
                "",
            ),
        )
        return MilvusPipeline._merge_text_splits(splits, chunk_size=chunk_size, overlap=overlap)

    @staticmethod
    def _recursive_text_splits(
        text: str,
        *,
        chunk_size: int,
        separators: tuple[str, ...],
    ) -> list[str]:
        value = str(text or "")
        if len(value.strip()) <= chunk_size:
            return [value] if value.strip() else []

        separator = ""
        remaining_separators: tuple[str, ...] = ("",)
        for index, candidate in enumerate(separators):
            if candidate == "" or candidate in value:
                separator = candidate
                remaining_separators = separators[index + 1 :] or ("",)
                break

        if separator == "":
            return [value] if value.strip() else []

        splits: list[str] = []
        for piece in MilvusPipeline._split_text_with_separator(value, separator):
            if not piece.strip():
                continue
            if len(piece.strip()) <= chunk_size:
                splits.append(piece)
            else:
                splits.extend(
                    MilvusPipeline._recursive_text_splits(
                        piece,
                        chunk_size=chunk_size,
                        separators=remaining_separators,
                    )
                )
        return splits

    @staticmethod
    def _split_text_with_separator(text: str, separator: str) -> list[str]:
        if not separator:
            return [text]
        parts = text.split(separator)
        splits: list[str] = []
        for index, part in enumerate(parts):
            if index < len(parts) - 1:
                splits.append(f"{part}{separator}")
            elif part:
                splits.append(part)
        return splits

    @staticmethod
    def _merge_text_splits(splits: list[str], *, chunk_size: int, overlap: int) -> list[str]:
        chunks: list[str] = []
        current = ""

        def emit(value: str) -> None:
            cleaned = value.strip()
            if cleaned:
                chunks.append(cleaned)

        for raw_piece in splits:
            piece = str(raw_piece or "")
            if not piece.strip():
                continue

            if len(piece.strip()) > chunk_size:
                emit(current)
                current = ""
                step = max(1, chunk_size - overlap)
                for start in range(0, len(piece), step):
                    emit(piece[start : start + chunk_size])
                continue

            candidate = f"{current}{piece}" if current else piece
            if len(candidate) <= chunk_size:
                current = candidate
                continue

            emit(current)
            max_prefix = max(0, chunk_size - len(piece))
            prefix_len = min(overlap, max_prefix)
            prefix = current[-prefix_len:] if prefix_len and current else ""
            current = f"{prefix}{piece}" if prefix else piece

        emit(current)
        return chunks

    @staticmethod
    def _varchar(value: Any, *, limit: int = 65535) -> str:
        text = str(value or "")
        return text if len(text) <= limit else text[:limit]

    @staticmethod
    def _text_preview(value: str, *, limit: int = 360) -> str:
        text = " ".join(str(value or "").split())
        return text if len(text) <= limit else text[: max(0, limit - 1)] + "…"

    def _chunk_row(self, chunk: _TextChunk, vector: list[float]) -> dict[str, Any]:
        metadata = dict(chunk.metadata)
        metadata["document_id"] = chunk.document_id
        metadata["doc_id"] = chunk.document_id
        metadata["ref_doc_id"] = chunk.document_id
        node_content = {
            "id_": chunk.node_id,
            "embedding": None,
            "metadata": metadata,
            "excluded_embed_metadata_keys": [],
            "excluded_llm_metadata_keys": [],
            "relationships": {
                "1": {
                    "node_id": chunk.document_id,
                    "node_type": "4",
                    "metadata": metadata,
                    "hash": hashlib.sha256(chunk.text.encode("utf-8")).hexdigest(),
                    "class_name": "RelatedNodeInfo",
                }
            },
            "metadata_template": "{key}: {value}",
            "metadata_separator": "\n",
            "text": chunk.text,
            "mimetype": "text/plain",
            "text_template": "{metadata_str}\n\n{content}",
            "class_name": "TextNode",
        }
        return {
            "id": self._varchar(chunk.node_id),
            "doc_id": self._varchar(chunk.document_id),
            "text": self._varchar(chunk.text),
            "embedding": vector,
            "file_name": self._varchar(metadata.get("file_name")),
            "file_path": self._varchar(metadata.get("file_path")),
            "relative_path": self._varchar(metadata.get("relative_path")),
            "document_id": self._varchar(chunk.document_id),
            "ref_doc_id": self._varchar(chunk.document_id),
            "document_key": self._varchar(metadata.get("relative_path") or metadata.get("file_name")),
            "source_type": self._varchar(metadata.get("source_type")),
            "chunk_index": chunk.chunk_index,
            "text_preview": self._text_preview(chunk.text),
            "text_chars": len(chunk.text),
            "_node_type": "TextNode",
            "_node_content": json.dumps(node_content, ensure_ascii=False),
            "metadata": json.dumps(metadata, ensure_ascii=False),
        }

    async def _http_rows_for_documents(
        self,
        documents: list[_LoadedDocument],
        *,
        progress_callback=None,
    ) -> list[dict[str, Any]]:
        chunks = self._split_http_documents(documents)
        if not chunks:
            return []
        texts = [chunk.text for chunk in chunks]
        embeddings = await get_embedding_client().embed(
            texts,
            progress_callback=progress_callback,
            input_type="search_document",
        )
        if len(embeddings) != len(chunks):
            raise RuntimeError(
                f"Embedding API returned {len(embeddings)} vectors for {len(chunks)} chunks."
            )
        embedding_cfg = get_embedding_config()
        rows: list[dict[str, Any]] = []
        for chunk, vector in zip(chunks, embeddings):
            if embedding_cfg.dim and len(vector) != embedding_cfg.dim:
                raise RuntimeError(
                    "Embedding dimension mismatch: "
                    f"configured EMBEDDING_DIMENSION={embedding_cfg.dim}, "
                    f"API returned {len(vector)}."
                )
            rows.append(self._chunk_row(chunk, vector))
        return rows

    def _http_insert_rows(self, collection_name: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        batch_size = _env_int("MILVUS_HTTP_INSERT_BATCH_SIZE", 100)
        inserted = 0
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            inserted += milvus_http.insert_entities(
                self._milvus_uri(),
                self._milvus_token(),
                collection_name,
                batch,
            )
        return inserted

    def _ensure_http_collection(
        self,
        collection_name: str,
        *,
        overwrite: bool,
        retrieval_mode: str = "dense",
    ) -> None:
        uri = self._milvus_uri()
        token = self._milvus_token()
        retrieval_mode = _normalize_retrieval_mode(retrieval_mode, "dense")
        exists = milvus_http.has_collection(uri, token, collection_name)
        if exists and overwrite:
            milvus_http.drop_collection(uri, token, collection_name)
            exists = False
        if not exists:
            if retrieval_mode == "hybrid":
                milvus_http.create_hybrid_collection(
                    uri,
                    token,
                    collection_name,
                    dim=get_embedding_config().dim,
                    metric_type=self._similarity_metric(),
                )
            else:
                milvus_http.create_dense_collection(
                    uri,
                    token,
                    collection_name,
                    dim=get_embedding_config().dim,
                    metric_type=self._similarity_metric(),
                )
        elif retrieval_mode == "hybrid" and not self._http_collection_supports_hybrid(
            collection_name
        ):
            raise RuntimeError(
                "Existing Milvus collection does not contain the BM25 sparse field "
                "required for true hybrid retrieval. Rebuild the knowledge base with "
                "overwrite enabled or delete the old dense collection first."
            )

    def _http_collection_supports_hybrid(self, collection_name: str) -> bool:
        description = milvus_http.describe_collection(
            self._milvus_uri(),
            self._milvus_token(),
            collection_name,
        )
        return self._description_supports_hybrid(description)

    @staticmethod
    def _description_supports_hybrid(description: dict[str, Any]) -> bool:
        fields = description.get("fields") if isinstance(description, dict) else []
        if not isinstance(fields, list):
            return False
        for field in fields:
            if not isinstance(field, dict):
                continue
            name = str(field.get("name") or field.get("fieldName") or "").lower()
            field_type = str(field.get("type") or field.get("dataType") or "").lower()
            if name == "sparse" or "sparsefloatvector" in field_type:
                return True
        return False

    async def _initialize_http(self, kb_name: str, file_paths: List[str], **kwargs) -> bool:
        progress_callback = kwargs.get("progress_callback")
        retrieval_mode = _resolve_retrieval_mode(kwargs.get("retrieval_mode") or kwargs.get("mode"))

        await self._verify_embedding_connectivity()
        documents = await self._load_http_documents(file_paths)
        if not documents:
            raise RuntimeError("No valid documents found after parsing uploaded files.")
        rows = await self._http_rows_for_documents(documents, progress_callback=progress_callback)
        if not rows:
            raise RuntimeError("No vector chunks were produced from the uploaded documents.")

        collection_name = self._collection_name(kb_name)
        self._ensure_http_collection(
            collection_name,
            overwrite=_env_bool("MILVUS_OVERWRITE_ON_INIT", True),
            retrieval_mode=retrieval_mode,
        )
        inserted = self._http_insert_rows(collection_name, rows)
        if inserted <= 0:
            raise RuntimeError("Milvus REST insert returned 0 rows.")
        milvus_http.load_collection(self._milvus_uri(), self._milvus_token(), collection_name)

        vector_count = self._collection_row_count(kb_name, retries=1, delay_seconds=0)
        if vector_count == 0:
            raise RuntimeError("Milvus collection contains 0 vector rows after REST indexing.")
        self._write_marker(
            kb_name,
            document_count=len(documents),
            retrieval_mode=retrieval_mode,
            vector_count=vector_count or inserted,
        )
        self.logger.info(
            "KB '%s' indexed via Milvus REST into collection '%s' (%s rows)",
            kb_name,
            collection_name,
            vector_count or inserted,
        )
        return True

    async def _add_documents_http(self, kb_name: str, file_paths: List[str], **kwargs) -> bool:
        progress_callback = kwargs.get("progress_callback")
        marker = self._read_marker(kb_name)
        retrieval_mode = self._marker_retrieval_mode(marker)

        await self._verify_embedding_connectivity()
        documents = await self._load_http_documents(file_paths)
        if not documents:
            self.logger.warning("No valid documents to add")
            return False
        rows = await self._http_rows_for_documents(documents, progress_callback=progress_callback)
        if not rows:
            self.logger.warning("No vector chunks produced for incremental add")
            return False

        collection_name = str(marker.get("collection_name") or self._collection_name(kb_name))
        self._ensure_http_collection(
            collection_name,
            overwrite=False,
            retrieval_mode=retrieval_mode,
        )
        inserted = self._http_insert_rows(collection_name, rows)
        if inserted <= 0:
            raise RuntimeError("Milvus REST insert returned 0 rows.")
        milvus_http.load_collection(self._milvus_uri(), self._milvus_token(), collection_name)

        previous_count = int(marker.get("document_count") or 0)
        vector_count = self._collection_row_count(kb_name, retries=1, delay_seconds=0)
        if vector_count == 0:
            raise RuntimeError("Milvus collection contains 0 vector rows after adding documents.")
        self._write_marker(
            kb_name,
            document_count=previous_count + len(documents),
            retrieval_mode=retrieval_mode,
            vector_count=vector_count or inserted,
        )
        return True

    @staticmethod
    def _default_milvus_uri() -> str:
        if platform.system().lower() == "windows":
            return "http://localhost:19530"
        return "./data/milvus/sparkweave.db"

    @staticmethod
    def _is_local_file_uri(uri: str) -> bool:
        return "://" not in uri and uri != ":memory:"

    def _milvus_uri(self) -> str:
        uri = _env("MILVUS_URI", self._default_milvus_uri()).strip()
        uri = uri or self._default_milvus_uri()
        if self._is_local_file_uri(uri):
            Path(uri).expanduser().parent.mkdir(parents=True, exist_ok=True)
        return uri

    def _milvus_token(self) -> str | None:
        return _env("MILVUS_TOKEN", "").strip() or None

    def _collection_prefix(self) -> str:
        raw = _env("MILVUS_COLLECTION_PREFIX", "sparkweave").strip() or "sparkweave"
        return self._sanitize_identifier(raw, fallback="sparkweave")[:48]

    def _similarity_metric(self) -> str:
        return _env("MILVUS_SIMILARITY_METRIC", "IP").strip() or "IP"

    @staticmethod
    def _sanitize_identifier(value: str, *, fallback: str) -> str:
        name = re.sub(r"[^0-9A-Za-z_]+", "_", value.strip())
        name = re.sub(r"_+", "_", name).strip("_")
        if not name:
            name = fallback
        if not re.match(r"^[A-Za-z_]", name):
            name = f"_{name}"
        return name

    def _collection_name(self, kb_name: str) -> str:
        safe = self._sanitize_identifier(kb_name, fallback="kb")
        digest = hashlib.sha1(kb_name.encode("utf-8")).hexdigest()[:10]
        return f"{self._collection_prefix()}_{safe}_{digest}"[:255]

    def _storage_dir(self, kb_name: str) -> Path:
        return Path(self.kb_base_dir) / kb_name / "milvus_storage"

    def _marker_path(self, kb_name: str) -> Path:
        return self._storage_dir(kb_name) / "metadata.json"

    def _legacy_storage_dir(self, kb_name: str) -> Path:
        return Path(self.kb_base_dir) / kb_name / "llamaindex_storage"

    def _has_legacy_storage(self, kb_name: str) -> bool:
        return self._legacy_storage_dir(kb_name).exists()

    def _hybrid_ranker_config(
        self,
        *,
        ranker: Any = None,
        dense_weight: Any = None,
        sparse_weight: Any = None,
        rrf_k: Any = None,
    ) -> tuple[str, dict[str, Any]]:
        ranker = _normalize_hybrid_ranker(ranker or _env("MILVUS_HYBRID_RANKER", "RRFRanker"))
        if ranker == "WeightedRanker":
            resolved_dense = _coerce_float(dense_weight, _env_float_default("MILVUS_DENSE_WEIGHT", 1.0))
            resolved_sparse = _coerce_float(sparse_weight, _env_float_default("MILVUS_SPARSE_WEIGHT", 0.6))
            return ranker, {"weights": [resolved_dense, resolved_sparse]}
        resolved_k = _coerce_positive_int(rrf_k, _env_int("MILVUS_HYBRID_RRF_K", 60))
        return ranker, {"k": resolved_k}

    def _vector_store_kwargs(
        self,
        kb_name: str,
        *,
        overwrite: bool,
        retrieval_mode: str = "dense",
        hybrid_ranker: Any = None,
        dense_weight: Any = None,
        sparse_weight: Any = None,
        rrf_k: Any = None,
    ) -> dict[str, Any]:
        embedding_cfg = get_embedding_config()
        kwargs: dict[str, Any] = {
            "uri": self._milvus_uri(),
            "collection_name": self._collection_name(kb_name),
            "dim": embedding_cfg.dim,
            "overwrite": overwrite,
            "similarity_metric": self._similarity_metric(),
            "consistency_level": _env("MILVUS_CONSISTENCY_LEVEL", "Strong").strip() or "Strong",
        }
        token = self._milvus_token()
        if token:
            kwargs["token"] = token
        if retrieval_mode == "hybrid":
            ranker, ranker_params = self._hybrid_ranker_config(
                ranker=hybrid_ranker,
                dense_weight=dense_weight,
                sparse_weight=sparse_weight,
                rrf_k=rrf_k,
            )
            kwargs.update(
                {
                    "enable_sparse": True,
                    "hybrid_ranker": ranker,
                    "hybrid_ranker_params": ranker_params,
                }
            )
        return kwargs

    def _create_vector_store(
        self,
        kb_name: str,
        *,
        overwrite: bool,
        retrieval_mode: str = "dense",
        hybrid_ranker: Any = None,
        dense_weight: Any = None,
        sparse_weight: Any = None,
        rrf_k: Any = None,
    ):
        try:
            from llama_index.vector_stores.milvus import MilvusVectorStore
        except ImportError as exc:
            raise ImportError(
                "Milvus RAG requires llama-index-vector-stores-milvus. "
                "Install requirements/server.txt or run: "
                "pip install llama-index-vector-stores-milvus pymilvus"
            ) from exc

        try:
            return MilvusVectorStore(
                **self._vector_store_kwargs(
                    kb_name,
                    overwrite=overwrite,
                    retrieval_mode=retrieval_mode,
                    hybrid_ranker=hybrid_ranker,
                    dense_weight=dense_weight,
                    sparse_weight=sparse_weight,
                    rrf_k=rrf_k,
                )
            )
        except Exception as exc:
            uri = self._milvus_uri()
            message = str(exc).lower()
            if self._is_local_file_uri(uri) and "milvus-lite" in message:
                raise RuntimeError(
                    "Milvus Lite local-file mode is not available in this Python "
                    "environment. On Windows, start a standalone Milvus service and "
                    "set MILVUS_URI=http://localhost:19530, or use WSL/Linux/macOS "
                    "for Milvus Lite."
                ) from exc
            raise

    def _write_marker(
        self,
        kb_name: str,
        *,
        document_count: int,
        retrieval_mode: str = "dense",
        vector_count: int | None = None,
    ) -> None:
        embedding_cfg = get_embedding_config()
        storage_dir = self._storage_dir(kb_name)
        storage_dir.mkdir(parents=True, exist_ok=True)
        retrieval_mode = _normalize_retrieval_mode(retrieval_mode, "dense")
        marker = {
            "schema_version": MILVUS_MARKER_SCHEMA_VERSION,
            "provider": self.provider,
            "kb_name": kb_name,
            "collection_name": self._collection_name(kb_name),
            "collection_prefix": self._collection_prefix(),
            "uri": self._milvus_uri(),
            "similarity_metric": self._similarity_metric(),
            "embedding_model": embedding_cfg.model,
            "embedding_dim": embedding_cfg.dim,
            "chunk_size": getattr(self, "chunk_size", _env_int("RAG_CHUNK_SIZE", 512)),
            "chunk_overlap": getattr(self, "chunk_overlap", _env_int("RAG_CHUNK_OVERLAP", 50)),
            "document_count": document_count,
            "vector_count": vector_count,
            "retrieval_mode": retrieval_mode,
            "enable_sparse": retrieval_mode == "hybrid",
            "created_by": "sparkweave.rag.milvus",
            "updated_at": datetime.now().isoformat(),
        }
        if vector_count is None:
            marker.pop("vector_count", None)
        if retrieval_mode == "hybrid":
            ranker, ranker_params = self._hybrid_ranker_config()
            marker["hybrid_ranker"] = ranker
            marker["hybrid_ranker_params"] = ranker_params
            marker["hybrid_backend"] = "milvus_bm25"
            marker["dense_field"] = "embedding"
            marker["sparse_field"] = "sparse"
            marker["text_field"] = "text"
        self._marker_path(kb_name).write_text(
            json.dumps(marker, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _read_marker(self, kb_name: str) -> dict[str, Any]:
        marker_path = self._marker_path(kb_name)
        if not marker_path.exists():
            return {}
        try:
            return json.loads(marker_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _search_failure_result(self, *, query: str, kb_name: str, exc: Exception) -> dict[str, Any]:
        """Build a user-facing failure payload for retrieval UIs and chat tools."""
        try:
            from sparkweave.services.rag_support.diagnostics import diagnose_rag

            diagnostic = diagnose_rag(
                kb_base_dir=self.kb_base_dir,
                kb_name=kb_name,
                check_connection=False,
            )
        except Exception:
            diagnostic = {}

        readiness = diagnostic.get("readiness") if isinstance(diagnostic, dict) else {}
        if not isinstance(readiness, dict):
            readiness = {}
        readiness = dict(readiness)
        if diagnostic.get("uri_mismatch"):
            readiness.setdefault("label", "地址不一致")
            readiness.setdefault(
                "summary",
                "知识库记录的 Milvus 地址与当前运行时地址不一致。",
            )
            readiness.setdefault(
                "primary_action",
                "统一 Milvus 运行模式后重建索引。",
            )
            readiness["state"] = "error"
            error_code = "milvus_uri_mismatch"
        else:
            readiness.setdefault("state", "error")
            readiness.setdefault("label", "连接异常")
            readiness.setdefault("summary", "RAG 后端暂时不可用，聊天会缺少知识库证据。")
            readiness.setdefault("primary_action", "检查 Milvus、Embedding 服务和网络连接。")
            error_code = "milvus_connection_error"

        summary = str(readiness.get("summary") or "RAG 检索暂时不可用。").strip()
        action = str(readiness.get("primary_action") or "请检查检索服务配置。").strip()
        answer = f"{summary} 下一步：{action}"
        diagnostic_summary = {
            "uri": diagnostic.get("uri"),
            "indexed_uri": diagnostic.get("indexed_uri"),
            "uri_mismatch": diagnostic.get("uri_mismatch"),
            "uri_mismatch_kind": diagnostic.get("uri_mismatch_kind"),
            "collection_name": diagnostic.get("collection_name"),
            "vector_row_count": diagnostic.get("vector_row_count"),
        }
        return {
            "query": query,
            "answer": answer,
            "content": "",
            "sources": [],
            "source_count": 0,
            "provider": self.provider,
            "success": False,
            "error": answer,
            "error_code": error_code,
            "error_detail": str(exc),
            "readiness": readiness,
            "diagnostic": diagnostic_summary,
        }

    @staticmethod
    def _marker_retrieval_mode(marker: dict[str, Any]) -> str:
        if marker.get("enable_sparse") is True:
            return "hybrid"
        return _normalize_retrieval_mode(marker.get("retrieval_mode"), "dense")

    def _collection_row_count(self, kb_name: str, *, retries: int = 3, delay_seconds: float = 0.4) -> int | None:
        collection_name = self._collection_name(kb_name)
        uri = self._milvus_uri()
        token = self._milvus_token()
        last_value: int | None = None
        for attempt in range(max(1, retries)):
            try:
                if milvus_http.is_http_uri(uri):
                    value = milvus_http.collection_row_count(uri, token, collection_name)
                else:
                    from pymilvus import MilvusClient

                    client = MilvusClient(uri=uri, token=token)
                    stats = client.get_collection_stats(collection_name)
                    value = _stats_row_count(stats)
                last_value = value
                if value is not None and value > 0:
                    return value
            except Exception as exc:
                self.logger.debug("Unable to read Milvus row count for %s: %s", collection_name, exc)
            if attempt < retries - 1:
                time.sleep(delay_seconds)
        return last_value

    async def _query_embedding(self, query: str) -> list[float]:
        vectors = await get_embedding_client().embed([query], input_type="search_query")
        if not vectors or not vectors[0]:
            raise RuntimeError("Embedding API returned an empty query vector.")
        return vectors[0]

    @staticmethod
    def _http_output_fields() -> list[str]:
        return [
            "text",
            "file_name",
            "file_path",
            "relative_path",
            "doc_id",
            "document_id",
            "ref_doc_id",
            "source_type",
            "page_label",
            "page",
            "section_title",
            "chunk_index",
            "text_preview",
            "text_chars",
            "_node_content",
        ]

    @staticmethod
    def _row_text_and_metadata(row: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        metadata = {
            key: row.get(key)
            for key in (
                "file_name",
                "file_path",
                "relative_path",
                "doc_id",
                "document_id",
                "ref_doc_id",
                "source_type",
                "page_label",
                "page",
                "section_title",
                "chunk_index",
                "text_preview",
                "text_chars",
            )
            if row.get(key) not in (None, "")
        }
        text = str(row.get("text") or "").strip()
        raw_node = row.get("_node_content")
        if isinstance(raw_node, str) and raw_node.strip():
            try:
                parsed = json.loads(raw_node)
            except json.JSONDecodeError:
                parsed = {}
            if isinstance(parsed, dict):
                parsed_metadata = parsed.get("metadata")
                if isinstance(parsed_metadata, dict):
                    metadata = {**parsed_metadata, **metadata}
                text = text or str(parsed.get("text") or "").strip()
        return text, metadata

    @classmethod
    def _rows_to_nodes(cls, rows: list[dict[str, Any]]) -> list[Any]:
        nodes: list[Any] = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            text, metadata = cls._row_text_and_metadata(row)
            if not text:
                continue
            node_id = str(row.get("id") or row.get("pk") or row.get("doc_id") or index)
            try:
                score = float(row.get("distance"))
            except (TypeError, ValueError):
                score = None
            nodes.append(
                SimpleNamespace(
                    score=score,
                    node=SimpleNamespace(
                        text=text,
                        metadata=metadata,
                        node_id=node_id,
                    ),
                )
            )
        return nodes

    async def _http_search_nodes(
        self,
        *,
        query: str,
        collection_name: str,
        limit: int,
        metric_type: str,
    ) -> list[Any]:
        vector = await self._query_embedding(query)
        payload = {
            "collectionName": collection_name,
            "data": [vector],
            "annsField": "embedding",
            "limit": max(1, int(limit)),
            "outputFields": self._http_output_fields(),
            "searchParams": {"metricType": metric_type, "params": {}},
        }
        response = milvus_http.rest_post(
            self._milvus_uri(),
            self._milvus_token(),
            "/v2/vectordb/entities/search",
            payload,
            timeout=30,
        )
        data = response.get("data")
        rows = data if isinstance(data, list) else []
        return self._rows_to_nodes(rows)

    async def _http_hybrid_search_nodes(
        self,
        *,
        query: str,
        collection_name: str,
        limit: int,
        metric_type: str,
        hybrid_ranker: str,
        hybrid_ranker_params: dict[str, Any],
    ) -> list[Any]:
        vector = await self._query_embedding(query)
        rows = milvus_http.hybrid_search_entities(
            self._milvus_uri(),
            self._milvus_token(),
            collection_name,
            dense_vector=vector,
            query_text=query,
            dense_field="embedding",
            sparse_field="sparse",
            output_fields=self._http_output_fields(),
            limit=limit,
            metric_type=metric_type,
            ranker=hybrid_ranker,
            ranker_params=hybrid_ranker_params,
        )
        return self._rows_to_nodes(rows)

    async def initialize(self, kb_name: str, file_paths: List[str], **kwargs) -> bool:
        progress_callback = kwargs.get("progress_callback")
        retrieval_mode = _resolve_retrieval_mode(kwargs.get("retrieval_mode") or kwargs.get("mode"))

        self.logger.info(
            "Initializing KB '%s' with %s files using Milvus (%s retrieval)",
            kb_name,
            len(file_paths),
            retrieval_mode,
        )
        if milvus_http.is_http_uri(self._milvus_uri()):
            try:
                return await self._initialize_http(kb_name, file_paths, **kwargs)
            except Exception as exc:
                self.logger.error("Failed to initialize Milvus KB via REST: %s", exc)
                import traceback

                self.logger.error(traceback.format_exc())
                raise RuntimeError(f"Milvus REST index initialization failed: {exc}") from exc

        Settings = None
        CustomEmbedding = None
        try:
            Settings, StorageContext, VectorStoreIndex, CustomEmbedding, _ = (
                self._configure_llamaindex_runtime()
            )
            await self._verify_embedding_connectivity()
            documents = await self._load_documents(file_paths)
            if not documents:
                raise RuntimeError("No valid documents found after parsing uploaded files.")

            if progress_callback and isinstance(Settings.embed_model, CustomEmbedding):
                Settings.embed_model.set_progress_callback(progress_callback)

            vector_store = self._create_vector_store(
                kb_name,
                overwrite=_env_bool("MILVUS_OVERWRITE_ON_INIT", True),
                retrieval_mode=retrieval_mode,
            )
            storage_context = StorageContext.from_defaults(vector_store=vector_store)

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: VectorStoreIndex.from_documents(
                    documents,
                    storage_context=storage_context,
                    show_progress=True,
                ),
            )
            vector_count = self._collection_row_count(kb_name)
            if vector_count == 0:
                raise RuntimeError(
                    "Milvus collection was created but contains 0 vector rows after indexing."
                )
            self._write_marker(
                kb_name,
                document_count=len(documents),
                retrieval_mode=retrieval_mode,
                vector_count=vector_count,
            )
            self.logger.info(
                "KB '%s' indexed into Milvus collection '%s'",
                kb_name,
                self._collection_name(kb_name),
            )
            return True
        except Exception as exc:
            self.logger.error("Failed to initialize Milvus KB: %s", exc)
            import traceback

            self.logger.error(traceback.format_exc())
            raise RuntimeError(f"Milvus index initialization failed: {exc}") from exc
        finally:
            if Settings is not None and CustomEmbedding is not None and isinstance(Settings.embed_model, CustomEmbedding):
                Settings.embed_model.set_progress_callback(None)

    async def search(self, query: str, kb_name: str, **kwargs) -> Dict[str, Any]:
        mode = kwargs.pop("mode", None)
        if mode is not None:
            kwargs.setdefault("retrieval_mode", mode)
        self.logger.info("Searching Milvus KB '%s' with query: %s...", kb_name, query[:50])

        marker = self._read_marker(kb_name)
        if not marker:
            has_legacy_storage = self._has_legacy_storage(kb_name)
            if has_legacy_storage:
                answer = (
                    "当前知识库仍是旧版本本地 LlamaIndex 索引，默认 Milvus 检索无法直接读取。"
                    "请在知识库页面执行“重建索引”，或运行 "
                    f"`sparkweave kb reindex {kb_name} --provider milvus`。"
                )
                error = "legacy_llamaindex_storage_needs_reindex"
            else:
                answer = "当前知识库还没有 Milvus 索引。请先上传资料并等待索引完成。"
                error = "no_milvus_collection_metadata"
            return {
                "query": query,
                "answer": answer,
                "content": "",
                "provider": self.provider,
                "success": False,
                "error": error,
                "needs_reindex": has_legacy_storage,
                "legacy_storage_present": has_legacy_storage,
            }

        try:
            top_k = _coerce_positive_int(kwargs.get("top_k"), _env_int("RAG_TOP_K", 5))
            candidate_top_k = _coerce_positive_int(
                kwargs.get("candidate_top_k"),
                _env_int("RAG_CANDIDATE_TOP_K", top_k),
            )
            candidate_top_k = max(candidate_top_k, top_k)
            max_context_chars = _coerce_positive_int(
                kwargs.get("max_context_chars"),
                _env_int("RAG_MAX_CONTEXT_CHARS", 8000),
            )
            score_threshold = _coerce_optional_float(
                kwargs.get("score_threshold"),
                _env_float("RAG_SCORE_THRESHOLD"),
            )
            indexed_mode = self._marker_retrieval_mode(marker)
            requested_mode = _resolve_retrieval_mode(
                kwargs.get("retrieval_mode"),
                default=indexed_mode,
            )
            actual_mode = "hybrid" if requested_mode == "hybrid" and indexed_mode == "hybrid" else "dense"
            fallback_reason = ""
            needs_reindex_for_hybrid = requested_mode == "hybrid" and indexed_mode != "hybrid"
            if needs_reindex_for_hybrid:
                fallback_reason = "dense_index_requires_reindex_for_true_hybrid"
            reranker = normalize_reranker(kwargs.get("reranker") or _env("RAG_RERANKER", "none"))
            hybrid_ranker = kwargs.get("hybrid_ranker")
            dense_weight = kwargs.get("dense_weight", kwargs.get("hybrid_dense_weight"))
            sparse_weight = kwargs.get("sparse_weight", kwargs.get("hybrid_sparse_weight"))
            rrf_k = kwargs.get("rrf_k", kwargs.get("hybrid_rrf_k"))
            resolved_hybrid_ranker, resolved_hybrid_ranker_params = self._hybrid_ranker_config(
                ranker=hybrid_ranker,
                dense_weight=dense_weight,
                sparse_weight=sparse_weight,
                rrf_k=rrf_k,
            )
            rerank_top_n = _coerce_positive_int(kwargs.get("rerank_top_n"), _env_int("RAG_RERANK_TOP_N", top_k))
            final_top_n = rerank_top_n if reranker != "none" else top_k
            rerank_config = RerankConfig(
                provider=reranker,
                top_n=final_top_n,
                lexical_weight=_coerce_float(
                    kwargs.get("rerank_lexical_weight"),
                    _env_float_default("RAG_RERANK_LEXICAL_WEIGHT", 0.35),
                ),
                vector_weight=_coerce_float(
                    kwargs.get("rerank_vector_weight"),
                    _env_float_default("RAG_RERANK_VECTOR_WEIGHT", 0.65),
                ),
            )
            collection_name = marker.get("collection_name", self._collection_name(kb_name))
            milvus_uri = self._milvus_uri()
            http_hybrid_lite = (
                milvus_http.is_http_uri(milvus_uri)
                and needs_reindex_for_hybrid
            )
            if http_hybrid_lite:
                if reranker == "none":
                    reranker = "keyword"
                    rerank_top_n = max(rerank_top_n, top_k)
                    final_top_n = rerank_top_n
                    rerank_config = RerankConfig(
                        provider=reranker,
                        top_n=final_top_n,
                        lexical_weight=_coerce_float(
                            kwargs.get("rerank_lexical_weight"),
                            _env_float_default("RAG_HYBRID_LITE_LEXICAL_WEIGHT", 0.75),
                        ),
                        vector_weight=_coerce_float(
                            kwargs.get("rerank_vector_weight"),
                            _env_float_default("RAG_HYBRID_LITE_VECTOR_WEIGHT", 0.25),
                        ),
                    )
            if milvus_http.is_http_uri(milvus_uri):
                if actual_mode == "hybrid":
                    nodes = await self._http_hybrid_search_nodes(
                        query=query,
                        collection_name=collection_name,
                        limit=candidate_top_k,
                        metric_type=str(marker.get("similarity_metric") or self._similarity_metric()),
                        hybrid_ranker=resolved_hybrid_ranker,
                        hybrid_ranker_params=resolved_hybrid_ranker_params,
                    )
                else:
                    nodes = await self._http_search_nodes(
                        query=query,
                        collection_name=collection_name,
                        limit=candidate_top_k,
                        metric_type=str(marker.get("similarity_metric") or self._similarity_metric()),
                    )
                nodes, rerank_trace = rerank_nodes(query, list(nodes), rerank_config)
                nodes = list(nodes)[:final_top_n]
                context_pack = build_context_pack(
                    query=query,
                    nodes=list(nodes),
                    max_context_chars=max_context_chars,
                    score_threshold=score_threshold,
                )
                content = context_pack.content
                return {
                    "query": query,
                    "answer": content,
                    "content": content,
                    "sources": context_pack.sources,
                    "provider": self.provider,
                    "collection_name": collection_name,
                    "retrieval_mode": actual_mode,
                    "requested_retrieval_mode": requested_mode,
                    "indexed_retrieval_mode": indexed_mode,
                    "hybrid_fallback_reason": fallback_reason,
                    "hybrid_lite_applied": http_hybrid_lite,
                    "needs_reindex_for_hybrid": needs_reindex_for_hybrid,
                    "hybrid_ranker": resolved_hybrid_ranker if actual_mode == "hybrid" else "",
                    "hybrid_ranker_params": resolved_hybrid_ranker_params if actual_mode == "hybrid" else {},
                    "top_k": top_k,
                    "candidate_top_k": candidate_top_k,
                    "score_threshold": score_threshold,
                    "reranker": rerank_trace.provider,
                    "rerank_applied": rerank_trace.applied,
                    "rerank_input_count": rerank_trace.input_count,
                    "rerank_output_count": rerank_trace.output_count,
                    "rerank_error": rerank_trace.error,
                    "context_pack": context_pack.trace,
                    "source_count": len(context_pack.sources),
                    "success": True,
                    "transport": "milvus_rest",
                }

            _, _, VectorStoreIndex, _, _ = self._llamaindex_runtime()
            vector_store = self._create_vector_store(
                kb_name,
                overwrite=False,
                retrieval_mode=indexed_mode,
                hybrid_ranker=resolved_hybrid_ranker,
                dense_weight=dense_weight,
                sparse_weight=sparse_weight,
                rrf_k=rrf_k,
            )
            loop = asyncio.get_event_loop()

            def load_and_retrieve():
                index = VectorStoreIndex.from_vector_store(vector_store)
                retriever_kwargs: dict[str, Any] = {"similarity_top_k": candidate_top_k}
                if actual_mode == "hybrid":
                    retriever_kwargs["vector_store_query_mode"] = "hybrid"
                try:
                    retriever = index.as_retriever(**retriever_kwargs)
                except TypeError:
                    retriever = index.as_retriever(similarity_top_k=candidate_top_k)
                return retriever.retrieve(query)

            nodes = await loop.run_in_executor(None, load_and_retrieve)
            nodes, rerank_trace = rerank_nodes(query, list(nodes), rerank_config)
            nodes = list(nodes)[:final_top_n]
            context_pack = build_context_pack(
                query=query,
                nodes=list(nodes),
                max_context_chars=max_context_chars,
                score_threshold=score_threshold,
            )
            content = context_pack.content
            return {
                "query": query,
                "answer": content,
                "content": content,
                "sources": context_pack.sources,
                "provider": self.provider,
                "collection_name": collection_name,
                "retrieval_mode": actual_mode,
                "requested_retrieval_mode": requested_mode,
                "indexed_retrieval_mode": indexed_mode,
                "hybrid_fallback_reason": fallback_reason,
                "needs_reindex_for_hybrid": needs_reindex_for_hybrid,
                "hybrid_ranker": resolved_hybrid_ranker if actual_mode == "hybrid" else "",
                "hybrid_ranker_params": resolved_hybrid_ranker_params if actual_mode == "hybrid" else {},
                "top_k": top_k,
                "candidate_top_k": candidate_top_k,
                "score_threshold": score_threshold,
                "reranker": rerank_trace.provider,
                "rerank_applied": rerank_trace.applied,
                "rerank_input_count": rerank_trace.input_count,
                "rerank_output_count": rerank_trace.output_count,
                "context_pack": context_pack.trace,
                "source_count": len(context_pack.sources),
                "success": True,
            }
        except Exception as exc:
            self.logger.debug("Milvus search failed: %s", exc)
            self.logger.debug("Milvus search traceback", exc_info=True)
            return self._search_failure_result(query=query, kb_name=kb_name, exc=exc)

    async def add_documents(self, kb_name: str, file_paths: List[str], **kwargs) -> bool:
        progress_callback = kwargs.get("progress_callback")
        self.logger.info("Adding %s documents to Milvus KB '%s'", len(file_paths), kb_name)

        if milvus_http.is_http_uri(self._milvus_uri()):
            try:
                return await self._add_documents_http(kb_name, file_paths, **kwargs)
            except Exception as exc:
                self.logger.error("Failed to add documents to Milvus KB via REST: %s", exc)
                import traceback

                self.logger.error(traceback.format_exc())
                return False

        Settings = None
        CustomEmbedding = None
        try:
            Settings, _, VectorStoreIndex, CustomEmbedding, _ = self._configure_llamaindex_runtime()
            await self._verify_embedding_connectivity()
            documents = await self._load_documents(file_paths)
            if not documents:
                self.logger.warning("No valid documents to add")
                return False

            if progress_callback and isinstance(Settings.embed_model, CustomEmbedding):
                Settings.embed_model.set_progress_callback(progress_callback)

            marker = self._read_marker(kb_name)
            retrieval_mode = self._marker_retrieval_mode(marker)
            vector_store = self._create_vector_store(
                kb_name,
                overwrite=False,
                retrieval_mode=retrieval_mode,
            )
            loop = asyncio.get_event_loop()

            def insert_documents():
                index = VectorStoreIndex.from_vector_store(vector_store)
                for doc in documents:
                    index.insert(doc)
                return len(documents)

            added = await loop.run_in_executor(None, insert_documents)
            previous_count = int(marker.get("document_count") or 0)
            vector_count = self._collection_row_count(kb_name)
            if vector_count == 0:
                raise RuntimeError(
                    "Milvus collection still contains 0 vector rows after adding documents."
                )
            self._write_marker(
                kb_name,
                document_count=previous_count + added,
                retrieval_mode=retrieval_mode,
                vector_count=vector_count,
            )
            return True
        except Exception as exc:
            self.logger.error("Failed to add documents to Milvus KB: %s", exc)
            import traceback

            self.logger.error(traceback.format_exc())
            return False
        finally:
            if Settings is not None and CustomEmbedding is not None and isinstance(Settings.embed_model, CustomEmbedding):
                Settings.embed_model.set_progress_callback(None)

    async def delete(self, kb_name: str) -> bool:
        collection_name = self._collection_name(kb_name)
        uri = self._milvus_uri()
        token = self._milvus_token()
        if milvus_http.is_http_uri(uri):
            try:
                if milvus_http.has_collection(uri, token, collection_name):
                    milvus_http.drop_collection(uri, token, collection_name)
                    self.logger.info("Dropped Milvus collection '%s' via REST", collection_name)
            except Exception as exc:
                self.logger.warning("Failed to drop Milvus collection '%s': %s", collection_name, exc)
        else:
            try:
                from pymilvus import MilvusClient

                client = MilvusClient(uri=uri, token=token)
                if client.has_collection(collection_name):
                    client.drop_collection(collection_name)
                    self.logger.info("Dropped Milvus collection '%s'", collection_name)
            except ImportError as exc:
                raise ImportError(
                    "Milvus delete requires pymilvus. Install requirements/server.txt."
                ) from exc
            except Exception as exc:
                self.logger.warning("Failed to drop Milvus collection '%s': %s", collection_name, exc)

        kb_dir = Path(self.kb_base_dir) / kb_name
        if kb_dir.exists():
            import shutil

            shutil.rmtree(kb_dir)
            return True
        return False
