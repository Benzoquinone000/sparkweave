"""
LlamaIndex Pipeline
===================

True LlamaIndex integration using official llama-index library.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from llama_index.core import (
    Document,
    Settings,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.bridge.pydantic import PrivateAttr

from sparkweave.services.embedding_support import get_embedding_client, get_embedding_config
from sparkweave.services.ocr import OcrUnavailable, is_ocr_configured, ocr_pdf, recognize_image
from sparkweave.services.rag_support.file_routing import DocumentType, FileTypeRouter

# Default knowledge base directory
DEFAULT_KB_BASE_DIR = str(
    Path(__file__).resolve().parent.parent.parent.parent.parent / "data" / "knowledge_bases"
)


def _env_int(name: str, default: int) -> int:
    raw = _env(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logging.getLogger("sparkweave.rag.llamaindex").warning("Ignoring invalid %s=%r", name, raw)
        return default
    return value if value > 0 else default


def _env(name: str, default: str = "") -> str:
    try:
        from sparkweave.services.config import get_env_store

        return get_env_store().get(name, default)
    except Exception:
        return os.getenv(name, default)


class CustomEmbedding(BaseEmbedding):
    """
    Custom embedding adapter for OpenAI-compatible APIs.

    Works with any OpenAI-compatible endpoint including:
    - Google Gemini (text-embedding-004)
    - OpenAI (text-embedding-ada-002, text-embedding-3-*)
    - Azure OpenAI
    - Local models with OpenAI-compatible API
    """

    _client: Any = PrivateAttr()
    _logger: Any = PrivateAttr()
    _progress_callback: Any = PrivateAttr(default=None)

    def __init__(self, **kwargs):
        progress_cb = kwargs.pop("progress_callback", None)
        super().__init__(**kwargs)
        self._client = get_embedding_client()
        self._logger = logging.getLogger("sparkweave.rag.custom_embedding")
        self._progress_callback = progress_cb

    def set_progress_callback(self, callback):
        """Set progress callback fn(batch_num, total_batches)."""
        self._progress_callback = callback

    @classmethod
    def class_name(cls) -> str:
        return "custom_embedding"

    def _run_in_new_loop(self, coro):
        """Run an async coroutine from sync context using a fresh event loop.

        Avoids nest_asyncio which can deadlock when called from thread pools
        inside a running server event loop.
        """
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    async def _aget_query_embedding(self, query: str) -> List[float]:
        """Get embedding for a query."""
        embeddings = await self._client.embed([query], input_type="search_query")
        return embeddings[0]

    async def _aget_text_embedding(self, text: str) -> List[float]:
        """Get embedding for a text."""
        embeddings = await self._client.embed([text], input_type="search_document")
        return embeddings[0]

    async def _aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts."""
        return await self._client.embed(
            texts, progress_callback=self._progress_callback, input_type="search_document"
        )

    def _get_query_embedding(self, query: str) -> List[float]:
        """Sync version - called by LlamaIndex sync API."""
        return self._run_in_new_loop(self._aget_query_embedding(query))

    def _get_text_embedding(self, text: str) -> List[float]:
        """Sync version - called by LlamaIndex sync API."""
        return self._run_in_new_loop(self._aget_text_embedding(text))

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Sync batch version - called by LlamaIndex for bulk embedding."""
        self._logger.info(f"Embedding {len(texts)} text chunks...")
        result = self._run_in_new_loop(self._aget_text_embeddings(texts))
        self._logger.info(f"Embedding complete: {len(result)} vectors")
        return result


class LlamaIndexPipeline:
    """
    True LlamaIndex pipeline using official llama-index library.

    Uses LlamaIndex's native components:
    - VectorStoreIndex for indexing
    - CustomEmbedding for OpenAI-compatible embeddings
    - SentenceSplitter for chunking
    - StorageContext for persistence
    """

    def __init__(self, kb_base_dir: Optional[str] = None):
        """
        Initialize LlamaIndex pipeline.

        Args:
            kb_base_dir: Base directory for knowledge bases
        """
        self.logger = logging.getLogger("sparkweave.rag.llamaindex")
        self.kb_base_dir = kb_base_dir or DEFAULT_KB_BASE_DIR
        self._configure_settings()

    def _configure_settings(self):
        """Configure LlamaIndex global settings."""
        embedding_cfg = get_embedding_config()

        Settings.embed_model = CustomEmbedding()
        Settings.chunk_size = 512
        Settings.chunk_overlap = 50

        self.logger.info(
            f"LlamaIndex configured: embedding={embedding_cfg.model} "
            f"({embedding_cfg.dim}D, {embedding_cfg.binding}), chunk_size=512"
        )

    @staticmethod
    def _relative_path_for_file(file_path: Path) -> str:
        """Return the KB raw-relative path when the file lives under raw/."""
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
        """Return the same stable id used by the document-management API."""
        import hashlib

        relative_path = cls._relative_path_for_file(file_path)
        return hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def _document_metadata(
        cls,
        file_path: Path,
        *,
        source_type: str = "",
    ) -> dict[str, str]:
        document_id = cls._document_id_for_file(file_path)
        relative_path = cls._relative_path_for_file(file_path)
        metadata = {
            "file_name": file_path.name,
            "file_path": str(file_path),
            "relative_path": relative_path,
            "document_id": document_id,
            "doc_id": document_id,
            "ref_doc_id": document_id,
        }
        if source_type:
            metadata["source_type"] = source_type
        return metadata

    @classmethod
    def _make_document(
        cls,
        *,
        text: str,
        file_path: Path,
        source_type: str = "",
    ) -> Document:
        document_id = cls._document_id_for_file(file_path)
        metadata = cls._document_metadata(file_path, source_type=source_type)
        try:
            return Document(text=text, id_=document_id, metadata=metadata)
        except TypeError:
            document = Document(text=text, metadata=metadata)
            try:
                document.id_ = document_id
            except Exception:
                pass
            return document

    async def _verify_embedding_connectivity(self) -> None:
        """Quick smoke-test: embed a single token to catch config/network issues early."""
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
                    f"but provider returned {actual_dim}. "
                    "Update the embedding dimension setting and rebuild the knowledge base."
                )
            self.logger.info(
                f"Embedding API OK (returned {actual_dim}-dim vector)"
            )
        except Exception as e:
            self.logger.error(f"Embedding API connectivity check failed: {e}")
            raise RuntimeError(
                f"Cannot reach embedding API. Please check your embedding configuration. Error: {e}"
            ) from e

    async def _load_documents(self, file_paths: List[str]) -> List[Document]:
        """Load supported files into LlamaIndex documents.

        Milvus and local LlamaIndex storage share the same ingestion behavior:
        PDFs go through the PDF/OCR parser, images go through OCR, text-like
        files are read directly, and unsupported files are skipped with a
        warning.
        """
        documents = []
        classification = FileTypeRouter.classify_files(file_paths)

        for file_path_str in classification.parser_files:
            file_path = Path(file_path_str)
            doc_type = FileTypeRouter.get_document_type(str(file_path))
            if doc_type == DocumentType.IMAGE:
                self.logger.info("Parsing image with OCR: %s", file_path.name)
                text = self._extract_image_text(file_path)
                source_type = "image_ocr"
            else:
                self.logger.info(f"Parsing PDF: {file_path.name}")
                text = self._extract_pdf_text(file_path)
                source_type = "pdf"
            if text.strip():
                documents.append(
                    self._make_document(
                        text=text,
                        file_path=file_path,
                        source_type=source_type,
                    )
                )
                self.logger.info(f"Loaded: {file_path.name} ({len(text)} chars)")
            else:
                self.logger.warning(f"Skipped empty document: {file_path.name}")

        for file_path_str in classification.text_files:
            file_path = Path(file_path_str)
            self.logger.info(f"Parsing text: {file_path.name}")
            text = await FileTypeRouter.read_text_file(str(file_path))
            if text.strip():
                documents.append(
                    self._make_document(
                        text=text,
                        file_path=file_path,
                    )
                )
                self.logger.info(f"Loaded: {file_path.name} ({len(text)} chars)")
            else:
                self.logger.warning(f"Skipped empty document: {file_path.name}")

        for file_path_str in classification.unsupported:
            self.logger.warning(f"Skipped unsupported file: {Path(file_path_str).name}")

        return documents

    async def initialize(self, kb_name: str, file_paths: List[str], **kwargs) -> bool:
        """
        Initialize KB using real LlamaIndex components.

        Args:
            kb_name: Knowledge base name
            file_paths: List of file paths to process
            **kwargs: Additional arguments (accepts progress_callback)

        Returns:
            True if successful
        """
        progress_callback = kwargs.get("progress_callback")

        self.logger.info(
            f"Initializing KB '{kb_name}' with {len(file_paths)} files using LlamaIndex"
        )

        kb_dir = Path(self.kb_base_dir) / kb_name
        storage_dir = kb_dir / "llamaindex_storage"
        storage_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Verify embedding API is reachable before doing any heavy work
            await self._verify_embedding_connectivity()

            documents = await self._load_documents(file_paths)

            if not documents:
                raise RuntimeError("No valid documents found after parsing uploaded files.")

            self.logger.info(
                f"Creating VectorStoreIndex with {len(documents)} documents "
                f"(chunking + embedding)..."
            )

            if progress_callback and isinstance(Settings.embed_model, CustomEmbedding):
                Settings.embed_model.set_progress_callback(progress_callback)

            loop = asyncio.get_event_loop()
            index = await loop.run_in_executor(
                None,
                lambda: VectorStoreIndex.from_documents(documents, show_progress=True),
            )

            # Persist index
            index.storage_context.persist(persist_dir=str(storage_dir))
            self.logger.info(f"Index persisted to {storage_dir}")

            self.logger.info(f"KB '{kb_name}' initialized successfully with LlamaIndex")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize KB: {e}")
            import traceback

            self.logger.error(traceback.format_exc())
            raise RuntimeError(f"LlamaIndex initialization failed: {e}") from e
        finally:
            if isinstance(Settings.embed_model, CustomEmbedding):
                Settings.embed_model.set_progress_callback(None)

    def _extract_pdf_text(self, file_path: Path) -> str:
        """Extract text from PDF.

        Strategy:
        - ``SPARKWEAVE_PDF_OCR_STRATEGY=ocr_first``: try configured OCR first,
          then fall back to the default PyMuPDF text-layer parser.
        - default/auto: use PyMuPDF first; if the extracted text is too short and
          OCR is configured, try OCR as a scanned-PDF fallback.
        """
        strategy = _env("SPARKWEAVE_PDF_OCR_STRATEGY", "auto").strip().lower()
        if strategy in {"iflytek_first", "ocr_first", "iflytek", "siliconflow_first", "deepseekocr_first"}:
            try:
                text = ocr_pdf(file_path)
                if text.strip():
                    self.logger.info("Extracted PDF text with OCR provider: %s", file_path.name)
                    return text
                self.logger.warning("OCR returned empty text for %s; falling back to PyMuPDF", file_path.name)
            except OcrUnavailable as exc:
                self.logger.warning("OCR unavailable for %s; falling back to PyMuPDF: %s", file_path.name, exc)
            return self._extract_pdf_text_default(file_path)

        text = self._extract_pdf_text_default(file_path)
        min_chars = _env_int("SPARKWEAVE_OCR_MIN_TEXT_CHARS", 40)
        if len(text.strip()) >= min_chars or not is_ocr_configured():
            return text

        try:
            ocr_text = ocr_pdf(file_path)
            if ocr_text.strip():
                self.logger.info("Used OCR fallback for scanned PDF: %s", file_path.name)
                return ocr_text
        except OcrUnavailable as exc:
            self.logger.warning("OCR fallback failed for %s: %s", file_path.name, exc)
        return text

    def _extract_pdf_text_default(self, file_path: Path) -> str:
        """Extract text from a PDF text layer using PyMuPDF."""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            texts = []
            for page in doc:
                texts.append(page.get_text())
            doc.close()
            return "\n\n".join(texts)
        except ImportError:
            self.logger.warning("PyMuPDF not installed. Cannot extract PDF text.")
            return ""
        except Exception as e:
            self.logger.error(f"Failed to extract PDF text: {e}")
            return ""

    def _extract_image_text(self, file_path: Path) -> str:
        """Extract text from an image using the configured OCR provider."""
        if not is_ocr_configured():
            self.logger.warning("OCR is not configured. Cannot parse image: %s", file_path.name)
            return ""

        encoding = file_path.suffix.lower().lstrip(".") or "png"
        if encoding == "jpg":
            encoding = "jpeg"
        try:
            text = recognize_image(file_path.read_bytes(), encoding=encoding)
            if text.strip():
                self.logger.info("Extracted image text with OCR provider: %s", file_path.name)
            else:
                self.logger.warning("OCR returned empty text for image: %s", file_path.name)
            return text
        except OcrUnavailable as exc:
            self.logger.warning("OCR unavailable for image %s: %s", file_path.name, exc)
            return ""
        except Exception as exc:
            self.logger.error("Failed to OCR image %s: %s", file_path.name, exc)
            return ""

    async def search(
        self,
        query: str,
        kb_name: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Search using LlamaIndex retriever.

        Args:
            query: Search query
            kb_name: Knowledge base name
            **kwargs: Additional arguments (top_k, etc.)

        Returns:
            Search results dictionary with answer, content, and sources
        """
        kwargs.pop("mode", None)
        self.logger.info(f"Searching KB '{kb_name}' with query: {query[:50]}...")

        kb_dir = Path(self.kb_base_dir) / kb_name
        storage_dir = kb_dir / "llamaindex_storage"

        docstore_path = storage_dir / "docstore.json"
        if not storage_dir.exists() or not docstore_path.exists():
            self.logger.warning(f"No LlamaIndex storage found at {storage_dir}")
            return {
                "query": query,
                "answer": "No documents indexed. Please upload documents first.",
                "content": "",
                "provider": "llamaindex",
                "success": False,
                "error": "no_documents_indexed",
            }

        embedding_mismatch_warning = ""
        try:
            import json as _json

            cfg_path = Path(self.kb_base_dir) / "kb_config.json"
            if cfg_path.exists():
                with open(cfg_path, encoding="utf-8") as _f:
                    kb_entry = _json.load(_f).get("knowledge_bases", {}).get(kb_name, {})
                if kb_entry.get("embedding_mismatch"):
                    stored = kb_entry.get("embedding_model", "unknown")
                    current = get_embedding_config().model
                    embedding_mismatch_warning = (
                        f"Warning: KB '{kb_name}' was indexed with '{stored}' "
                        f"but current model is '{current}'. Re-index recommended."
                    )
                    self.logger.warning(embedding_mismatch_warning)
        except Exception:
            pass

        try:
            # Load index from storage (run in thread pool)
            loop = asyncio.get_event_loop()

            def load_and_retrieve():
                storage_context = StorageContext.from_defaults(persist_dir=str(storage_dir))
                index = load_index_from_storage(storage_context)
                top_k = kwargs.get("top_k", 5)

                # Use retriever instead of query_engine to avoid LLM requirement
                retriever = index.as_retriever(similarity_top_k=top_k)
                nodes = retriever.retrieve(query)
                return nodes

            # Execute retrieval in thread pool to avoid blocking
            nodes = await loop.run_in_executor(None, load_and_retrieve)

            context_parts = []
            sources = []
            for i, node in enumerate(nodes):
                context_parts.append(node.node.text)
                meta = node.node.metadata or {}
                sources.append({
                    "title": meta.get("file_name", meta.get("title", f"Document {i + 1}")),
                    "content": node.node.text[:200],
                    "source": meta.get("file_path", meta.get("file_name", "")),
                    "page": meta.get("page_label", meta.get("page", "")),
                    "chunk_id": node.node.node_id or str(i),
                    "score": round(node.score, 4) if node.score is not None else "",
                })

            content = "\n\n".join(context_parts) if context_parts else ""

            result: Dict[str, Any] = {
                "query": query,
                "answer": content,
                "content": content,
                "sources": sources,
                "provider": "llamaindex",
                "success": True,
            }
            if embedding_mismatch_warning:
                result["warning"] = embedding_mismatch_warning
            return result

        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            import traceback

            self.logger.error(traceback.format_exc())
            return {
                "query": query,
                "answer": f"Search failed: {str(e)}",
                "content": "",
                "provider": "llamaindex",
                "success": False,
                "error": str(e),
            }

    async def add_documents(self, kb_name: str, file_paths: List[str], **kwargs) -> bool:
        """
        Incrementally add documents to an existing LlamaIndex KB.

        If the storage directory exists, loads the existing index and inserts
        new documents. Otherwise, creates a new index.

        Args:
            kb_name: Knowledge base name
            file_paths: List of file paths to add
            **kwargs: Additional arguments (accepts progress_callback)

        Returns:
            True if successful
        """
        progress_callback = kwargs.get("progress_callback")

        self.logger.info(f"Adding {len(file_paths)} documents to KB '{kb_name}' using LlamaIndex")

        kb_dir = Path(self.kb_base_dir) / kb_name
        storage_dir = kb_dir / "llamaindex_storage"

        try:
            await self._verify_embedding_connectivity()

            if progress_callback and isinstance(Settings.embed_model, CustomEmbedding):
                Settings.embed_model.set_progress_callback(progress_callback)

            documents = await self._load_documents(file_paths)

            if not documents:
                self.logger.warning("No valid documents to add")
                return False

            loop = asyncio.get_event_loop()

            if storage_dir.exists():
                self.logger.info(f"Loading existing index from {storage_dir}...")

                def load_and_insert():
                    storage_context = StorageContext.from_defaults(persist_dir=str(storage_dir))
                    index = load_index_from_storage(storage_context)

                    for i, doc in enumerate(documents, 1):
                        self.logger.info(
                            f"Inserting document {i}/{len(documents)}: "
                            f"{doc.metadata.get('file_name', 'unknown')}"
                        )
                        index.insert(doc)

                    index.storage_context.persist(persist_dir=str(storage_dir))
                    return len(documents)

                num_added = await loop.run_in_executor(None, load_and_insert)
                self.logger.info(f"Added {num_added} documents to existing index")
            else:
                self.logger.info(f"Creating new index with {len(documents)} documents...")
                storage_dir.mkdir(parents=True, exist_ok=True)

                def create_index():
                    index = VectorStoreIndex.from_documents(documents, show_progress=True)
                    index.storage_context.persist(persist_dir=str(storage_dir))
                    return len(documents)

                num_added = await loop.run_in_executor(None, create_index)
                self.logger.info(f"Created new index with {num_added} documents")

            self.logger.info(f"Successfully added documents to KB '{kb_name}'")
            return True

        except Exception as e:
            self.logger.error(f"Failed to add documents: {e}")
            import traceback

            self.logger.error(traceback.format_exc())
            return False
        finally:
            if isinstance(Settings.embed_model, CustomEmbedding):
                Settings.embed_model.set_progress_callback(None)

    async def delete(self, kb_name: str) -> bool:
        """
        Delete knowledge base.

        Args:
            kb_name: Knowledge base name

        Returns:
            True if successful
        """
        import shutil

        kb_dir = Path(self.kb_base_dir) / kb_name

        if kb_dir.exists():
            shutil.rmtree(kb_dir)
            self.logger.info(f"Deleted KB '{kb_name}'")
            return True

        return False

