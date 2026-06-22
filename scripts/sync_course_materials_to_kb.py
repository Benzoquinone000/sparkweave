#!/usr/bin/env python
"""Stage course template materials into SparkWeave knowledge bases."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE_DIR = ROOT / "data" / "course_templates"
DEFAULT_KB_DIR = ROOT / "data" / "knowledge_bases"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sparkweave.services.rag_support.factory import DEFAULT_PROVIDER, normalize_provider_name  # noqa: E402
from sparkweave.services.rag_support.file_routing import DocumentType, FileTypeRouter  # noqa: E402


@dataclass
class CourseMaterialSyncResult:
    template_id: str
    course_name: str
    kb_name: str
    template_path: Path
    copied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
    collisions: list[str] = field(default_factory=list)
    raw_document_count: int = 0
    needs_reindex: bool = False

    @property
    def has_errors(self) -> bool:
        return bool(self.missing or self.unsupported or self.collisions)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_material_path(project_root: Path, material: str) -> Path:
    path = Path(material)
    if path.is_absolute():
        return path
    return project_root / path


def _safe_kb_name(template: dict[str, Any], fallback: str) -> str:
    for key in ("knowledge_base_name", "course_name", "title", "id"):
        value = str(template.get(key) or "").strip()
        if value:
            if value.startswith("完整课程："):
                value = value.replace("完整课程：", "", 1).strip()
            return value
    return fallback


def _index_matches_raw(kb_dir: Path, raw_document_count: int) -> bool:
    milvus_marker = kb_dir / "milvus_storage" / "metadata.json"
    if milvus_marker.exists():
        marker = _load_json(milvus_marker, {})
        if isinstance(marker, dict) and marker.get("document_count") is not None:
            try:
                return int(marker.get("document_count")) == raw_document_count
            except (TypeError, ValueError):
                return False
        return raw_document_count > 0

    llama_marker = kb_dir / "llamaindex_storage" / "docstore.json"
    if llama_marker.exists():
        return raw_document_count > 0

    return False


def _raw_documents(raw_dir: Path) -> list[Path]:
    files: list[Path] = []
    if not raw_dir.exists():
        return files
    for pattern in FileTypeRouter.get_glob_patterns():
        files.extend(path for path in raw_dir.glob(pattern) if path.is_file())
    return sorted({path.resolve() for path in files}, key=lambda path: path.name.lower())


def discover_course_templates(template_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    templates: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(template_dir.rglob("*.json")):
        payload = _load_json(path, {})
        if isinstance(payload, dict) and isinstance(payload.get("source_materials"), list):
            templates.append((path, payload))
    return templates


def stage_course_materials(
    *,
    template_path: Path,
    template: dict[str, Any],
    project_root: Path,
    kb_base_dir: Path,
    rag_provider: str,
    overwrite: bool = False,
) -> CourseMaterialSyncResult:
    template_id = str(template.get("id") or template_path.stem).strip()
    course_name = str(template.get("course_name") or template.get("title") or template_id).strip()
    kb_name = _safe_kb_name(template, course_name or template_id)
    kb_dir = kb_base_dir / kb_name
    raw_dir = kb_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    result = CourseMaterialSyncResult(
        template_id=template_id,
        course_name=course_name,
        kb_name=kb_name,
        template_path=template_path,
    )

    for item in template.get("source_materials") or []:
        material = str(item).strip()
        if not material:
            continue
        source = _resolve_material_path(project_root, material)
        if not source.exists() or not source.is_file():
            result.missing.append(material)
            continue
        if FileTypeRouter.get_document_type(str(source)) == DocumentType.UNKNOWN:
            result.unsupported.append(material)
            continue

        destination = raw_dir / source.name
        if destination.exists():
            if _sha256(destination) == _sha256(source):
                result.skipped.append(destination.name)
                continue
            if not overwrite:
                result.collisions.append(destination.name)
                continue

        shutil.copy2(source, destination)
        result.copied.append(destination.name)

    raw_documents = _raw_documents(raw_dir)
    existing_metadata = _load_json(kb_dir / "metadata.json", {})
    previous_needs_reindex = (
        bool(existing_metadata.get("needs_reindex")) if isinstance(existing_metadata, dict) else False
    )
    result.raw_document_count = len(raw_documents)
    result.needs_reindex = (
        bool(result.copied)
        or previous_needs_reindex
        or not _index_matches_raw(kb_dir, len(raw_documents))
    )

    _update_kb_metadata(
        kb_dir=kb_dir,
        template=template,
        template_path=template_path,
        kb_name=kb_name,
        raw_documents=raw_documents,
        rag_provider=rag_provider,
        needs_reindex=result.needs_reindex,
    )
    return result


def _update_kb_metadata(
    *,
    kb_dir: Path,
    template: dict[str, Any],
    template_path: Path,
    kb_name: str,
    raw_documents: list[Path],
    rag_provider: str,
    needs_reindex: bool,
) -> None:
    metadata_path = kb_dir / "metadata.json"
    existing = _load_json(metadata_path, {})
    if not isinstance(existing, dict):
        existing = {}

    file_hashes = {}
    for document in raw_documents:
        file_hashes[document.name] = _sha256(document)

    metadata = {
        **existing,
        "name": kb_name,
        "created_at": existing.get("created_at") or _now(),
        "description": existing.get("description") or f"Course knowledge base: {kb_name}",
        "version": existing.get("version") or "1.0",
        "rag_provider": normalize_provider_name(rag_provider),
        "needs_reindex": bool(needs_reindex),
        "last_updated": _now(),
        "course_template_id": str(template.get("id") or template_path.stem),
        "course_id": str(template.get("course_id") or ""),
        "course_name": str(template.get("course_name") or kb_name),
        "source_template": (
            template_path.relative_to(ROOT).as_posix()
            if template_path.is_relative_to(ROOT)
            else str(template_path)
        ),
        "source_material_count": len(template.get("source_materials") or []),
        "raw_document_count": len(raw_documents),
        "file_hashes": file_hashes,
    }
    _write_json(metadata_path, metadata)


def update_kb_config(
    *,
    kb_base_dir: Path,
    results: list[CourseMaterialSyncResult],
    rag_provider: str,
) -> None:
    config_path = kb_base_dir / "kb_config.json"
    config = _load_json(config_path, {})
    if not isinstance(config, dict):
        config = {}

    defaults = config.setdefault("defaults", {})
    defaults.setdefault("rag_provider", normalize_provider_name(rag_provider))
    defaults.setdefault("search_mode", "hybrid")
    if results and not str(defaults.get("default_kb") or "").strip():
        defaults["default_kb"] = results[0].kb_name

    knowledge_bases = config.setdefault("knowledge_bases", {})
    for result in results:
        entry = knowledge_bases.setdefault(result.kb_name, {})
        entry.update(
            {
                "path": result.kb_name,
                "description": entry.get("description") or f"Course knowledge base: {result.kb_name}",
                "status": "needs_reindex" if result.needs_reindex else entry.get("status") or "ready",
                "updated_at": _now(),
                "rag_provider": normalize_provider_name(rag_provider),
                "needs_reindex": bool(result.needs_reindex),
                "course_template_id": result.template_id,
                "course_name": result.course_name,
                "raw_document_count": result.raw_document_count,
                "progress": {
                    "stage": "staged" if result.needs_reindex else "ready",
                    "message": (
                        "Course materials staged. Rebuild the index before RAG search."
                        if result.needs_reindex
                        else "Course materials are already staged."
                    ),
                    "percent": 100,
                    "current": result.raw_document_count,
                    "total": result.raw_document_count,
                    "timestamp": _now(),
                },
            }
        )

    _write_json(config_path, config)


async def _reindex_results(
    *,
    results: list[CourseMaterialSyncResult],
    kb_base_dir: Path,
    rag_provider: str,
) -> None:
    from sparkweave.knowledge.reindex import reindex_knowledge_base

    for result in results:
        if result.has_errors:
            continue
        count = await reindex_knowledge_base(
            result.kb_name,
            base_dir=kb_base_dir,
            rag_provider=rag_provider,
            backup=True,
        )
        print(f"[indexed] {result.kb_name}: {count} raw document(s)")


def _print_summary(results: list[CourseMaterialSyncResult]) -> None:
    for result in results:
        print(
            "[course-kb] "
            f"{result.kb_name}: copied={len(result.copied)}, "
            f"skipped={len(result.skipped)}, raw={result.raw_document_count}, "
            f"needs_reindex={str(result.needs_reindex).lower()}"
        )
        if result.missing:
            print(f"  missing: {', '.join(result.missing)}")
        if result.unsupported:
            print(f"  unsupported: {', '.join(result.unsupported)}")
        if result.collisions:
            print(f"  changed existing files: {', '.join(result.collisions)}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy course template source_materials into data/knowledge_bases/<course>/raw."
    )
    parser.add_argument("--template-dir", type=Path, default=DEFAULT_TEMPLATE_DIR)
    parser.add_argument("--kb-base-dir", type=Path, default=DEFAULT_KB_DIR)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--template-id", help="Only sync one template id.")
    parser.add_argument("--provider", default=DEFAULT_PROVIDER, help="RAG provider to record or use.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite changed files with the same name.")
    parser.add_argument("--index", action="store_true", help="Rebuild the RAG index after staging files.")
    parser.add_argument(
        "--stage-only",
        action="store_true",
        help="Only copy files and mark knowledge bases for reindex. This is the default.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rag_provider = normalize_provider_name(args.provider)
    template_filter = str(args.template_id or "").strip().lower()

    discovered = discover_course_templates(args.template_dir)
    if template_filter:
        discovered = [
            (path, template)
            for path, template in discovered
            if str(template.get("id") or path.stem).strip().lower() == template_filter
        ]

    if not discovered:
        print("No course templates with source_materials were found.", file=sys.stderr)
        return 1

    results = [
        stage_course_materials(
            template_path=path,
            template=template,
            project_root=args.project_root,
            kb_base_dir=args.kb_base_dir,
            rag_provider=rag_provider,
            overwrite=args.overwrite,
        )
        for path, template in discovered
    ]

    update_kb_config(kb_base_dir=args.kb_base_dir, results=results, rag_provider=rag_provider)
    _print_summary(results)

    if any(result.has_errors for result in results):
        return 1

    if args.index:
        asyncio.run(
            _reindex_results(
                results=results,
                kb_base_dir=args.kb_base_dir,
                rag_provider=rag_provider,
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
