#!/usr/bin/env python
"""Incrementally add documents to an existing knowledge base."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil

from dotenv import load_dotenv

from sparkweave.logging import get_logger
from sparkweave.services.rag_support.factory import (
    DEFAULT_PROVIDER,
    get_pipeline,
    normalize_provider_name,
)

logger = get_logger("KnowledgeInit")

DEFAULT_BASE_DIR = "./data/knowledge_bases"


class DocumentAddError(RuntimeError):
    """Base error for incremental document add failures."""


class DocumentNameCollisionError(DocumentAddError):
    """Raised when a different document already exists under the same raw filename."""


class DocumentIndexingError(DocumentAddError):
    """Raised when no staged document could be indexed successfully."""


class DocumentAdder:
    """Add documents to an existing knowledge base."""

    def __init__(
        self,
        kb_name: str,
        base_dir: str = DEFAULT_BASE_DIR,
        progress_tracker=None,
        rag_provider: str | None = None,
    ):
        self.kb_name = kb_name
        self.base_dir = Path(base_dir)
        self.kb_dir = self.base_dir / kb_name

        if not self.kb_dir.exists():
            raise ValueError(f"Knowledge base does not exist: {kb_name}")

        self.raw_dir = self.kb_dir / "raw"
        self.llamaindex_storage_dir = self.kb_dir / "llamaindex_storage"
        self.milvus_storage_dir = self.kb_dir / "milvus_storage"
        self.legacy_rag_storage_dir = self.kb_dir / "rag_storage"
        self.metadata_file = self.kb_dir / "metadata.json"
        self.rag_provider = self._resolve_provider(rag_provider)

        if not self._storage_dir().exists() and self.legacy_rag_storage_dir.exists():
            raise ValueError(
                f"Knowledge base '{kb_name}' uses legacy index format and requires reindex before incremental add"
            )

        if not self._storage_dir().exists():
            raise ValueError(
                f"Knowledge base not initialized ({self.rag_provider}): {kb_name}"
            )

        self.progress_tracker = progress_tracker

        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_provider(self, requested: str | None) -> str:
        if requested:
            return normalize_provider_name(requested)
        if self.metadata_file.exists():
            try:
                metadata = json.loads(self.metadata_file.read_text(encoding="utf-8"))
                return normalize_provider_name(metadata.get("rag_provider") or DEFAULT_PROVIDER)
            except Exception:
                pass
        return DEFAULT_PROVIDER

    def _storage_dir(self) -> Path:
        if self.rag_provider == "llamaindex":
            return self.llamaindex_storage_dir
        return self.milvus_storage_dir

    def _get_file_hash(self, file_path: Path) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def get_ingested_hashes(self) -> dict[str, str]:
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("file_hashes", {})
            except Exception:
                return {}
        return {}

    def add_documents(self, source_files: list[str], allow_duplicates: bool = False) -> list[Path]:
        """Validate and stage files into raw/ before indexing."""
        logger.info(f"Validating documents for '{self.kb_name}'...")

        ingested_hashes = self.get_ingested_hashes()
        files_to_process: list[Path] = []

        for source in source_files:
            source_path = Path(source)
            if not source_path.exists() or not source_path.is_file():
                logger.warning(f"Missing file: {source}")
                continue

            current_hash = self._get_file_hash(source_path)
            if current_hash in ingested_hashes.values() and not allow_duplicates:
                logger.info(f"Skipped (content already indexed): {source_path.name}")
                continue

            dest_path = self.raw_dir / source_path.name
            if dest_path.exists():
                dest_hash = self._get_file_hash(dest_path)
                if dest_hash == current_hash:
                    logger.info(f"Recovering staged file: {source_path.name}")
                    files_to_process.append(dest_path)
                    continue
                if not allow_duplicates:
                    raise DocumentNameCollisionError(
                        f"File name collision for '{source_path.name}': a different file "
                        "with the same name already exists in this knowledge base. "
                        "Rename the file or rebuild the knowledge base to replace it."
                    )

            shutil.copy2(source_path, dest_path)
            logger.info(f"Staged to raw: {source_path.name}")
            files_to_process.append(dest_path)

        return files_to_process

    async def process_new_documents(self, new_files: list[Path]) -> list[Path]:
        """Index staged files via the configured RAG provider."""
        if not new_files:
            return []

        pipeline = get_pipeline(self.rag_provider, kb_base_dir=str(self.base_dir))
        processed_files: list[Path] = []
        total_files = len(new_files)

        for idx, doc_file in enumerate(new_files, 1):
            try:
                if self.progress_tracker is not None:
                    from sparkweave.knowledge.progress_tracker import ProgressStage

                    self.progress_tracker.update(
                        ProgressStage.PROCESSING_FILE,
                        f"Indexing ({self.rag_provider}) {doc_file.name}",
                        current=idx,
                        total=total_files,
                    )

                progress_kwargs = {}
                if self.progress_tracker is not None:
                    from sparkweave.knowledge.progress_tracker import ProgressStage

                    def _on_progress(batch_num, total_batches, *, file_name=doc_file.name):
                        self.progress_tracker.update(
                            ProgressStage.PROCESSING_FILE,
                            f"Embedding {file_name}: batch {batch_num}/{total_batches}",
                            current=batch_num,
                            total=total_batches,
                            file_name=file_name,
                        )

                    progress_kwargs["progress_callback"] = _on_progress

                success = await pipeline.add_documents(
                    self.kb_name,
                    [str(doc_file)],
                    **progress_kwargs,
                )
                if success:
                    processed_files.append(doc_file)
                    self._record_successful_hash(doc_file)
                    logger.info(f"Processed ({self.rag_provider}): {doc_file.name}")
                else:
                    logger.error(f"Failed to index: {doc_file.name}")
            except Exception as e:
                logger.exception(f"Failed {doc_file.name}: {e}")

        return processed_files

    def _record_successful_hash(self, file_path: Path) -> None:
        file_hash = self._get_file_hash(file_path)

        metadata: dict = {}
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            except Exception:
                metadata = {}

        metadata.setdefault("file_hashes", {})[file_path.name] = file_hash
        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def update_metadata(self, added_count: int) -> None:
        """Update metadata after incremental add."""
        metadata: dict = {}
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            except Exception:
                metadata = {}

        metadata["rag_provider"] = self.rag_provider
        metadata["needs_reindex"] = False
        metadata["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        history = metadata.get("update_history", [])
        history.append(
            {
                "timestamp": metadata["last_updated"],
                "action": "incremental_add",
                "count": added_count,
                "provider": self.rag_provider,
            }
        )
        metadata["update_history"] = history

        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)


async def add_documents(
    kb_name: str,
    source_files: list[str],
    base_dir: str = DEFAULT_BASE_DIR,
    allow_duplicates: bool = False,
) -> int:
    """Convenience function used by CLI wrappers."""
    from sparkweave.knowledge.manager import KnowledgeBaseManager

    manager = KnowledgeBaseManager(base_dir=base_dir)
    try:
        manager.update_kb_status(
            name=kb_name,
            status="processing",
            progress={
                "stage": "processing_documents",
                "message": "Processing uploaded documents...",
                "percent": 0,
                "current": 0,
                "total": max(len(source_files), 1),
                "file_name": "",
                "error": None,
                "timestamp": datetime.now().isoformat(),
            },
        )

        adder = DocumentAdder(
            kb_name=kb_name,
            base_dir=base_dir,
            rag_provider=DEFAULT_PROVIDER,
        )
        new_files = adder.add_documents(source_files, allow_duplicates=allow_duplicates)
        if not new_files:
            manager.update_kb_status(
                name=kb_name,
                status="ready",
                progress={
                    "stage": "completed",
                    "message": "No new unique documents to process.",
                    "percent": 100,
                    "current": 1,
                    "total": 1,
                    "file_name": "",
                    "error": None,
                    "timestamp": datetime.now().isoformat(),
                },
            )
            return 0
        processed = await adder.process_new_documents(new_files)
        if new_files and not processed:
            raise DocumentIndexingError("No staged documents were indexed successfully.")
        adder.update_metadata(len(processed))

        manager.update_kb_status(
            name=kb_name,
            status="ready",
            progress={
                "stage": "completed",
                "message": f"Successfully processed {len(processed)} files!",
                "percent": 100,
                "current": len(processed),
                "total": max(len(new_files), 1),
                "file_name": "",
                "error": None,
                "timestamp": datetime.now().isoformat(),
            },
        )
        return len(processed)
    except Exception as exc:
        manager.update_kb_status(
            name=kb_name,
            status="error",
            progress={
                "stage": "error",
                "message": "Document upload failed",
                "percent": 0,
                "current": 0,
                "total": max(len(source_files), 1),
                "file_name": "",
                "error": str(exc),
                "timestamp": datetime.now().isoformat(),
            },
        )
        raise


async def main() -> None:
    parser = argparse.ArgumentParser(description="Incrementally add documents to a KB")
    parser.add_argument("kb_name", help="KB Name")
    parser.add_argument("--docs", nargs="+", help="Files")
    parser.add_argument("--docs-dir", help="Directory")
    parser.add_argument("--base-dir", default=DEFAULT_BASE_DIR)
    parser.add_argument("--allow-duplicates", action="store_true")

    args = parser.parse_args()
    load_dotenv()

    doc_files: list[str] = []
    if args.docs:
        doc_files.extend(args.docs)
    if args.docs_dir:
        p = Path(args.docs_dir)
        for ext in ["*.pdf", "*.txt", "*.md", "*.json", "*.csv"]:
            doc_files.extend([str(f) for f in p.glob(ext)])

    if not doc_files:
        logger.error("No documents provided.")
        return

    processed_count = await add_documents(
        kb_name=args.kb_name,
        source_files=doc_files,
        base_dir=args.base_dir,
        allow_duplicates=args.allow_duplicates,
    )

    if processed_count:
        logger.info(f"Done! Successfully added {processed_count} documents.")
    else:
        logger.info("No new unique documents to add.")


if __name__ == "__main__":
    asyncio.run(main())


