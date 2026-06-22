from __future__ import annotations

import json
from pathlib import Path

from scripts.sync_course_materials_to_kb import (
    discover_course_templates,
    stage_course_materials,
    update_kb_config,
)


def test_sync_course_materials_stages_raw_files_and_marks_reindex(tmp_path: Path) -> None:
    project_root = tmp_path
    template_dir = project_root / "data" / "course_templates" / "demo"
    kb_base_dir = project_root / "data" / "knowledge_bases"
    material = project_root / "ppts" / "demo" / "lesson.pdf"
    material.parent.mkdir(parents=True)
    material.write_bytes(b"%PDF-1.4\nfake lesson\n")

    template_path = template_dir / "demo_course.json"
    template_path.parent.mkdir(parents=True)
    template_path.write_text(
        json.dumps(
            {
                "id": "demo_course",
                "course_id": "DEMO101",
                "course_name": "演示课程",
                "knowledge_base_name": "演示课程资料",
                "source_materials": ["ppts/demo/lesson.pdf"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    templates = discover_course_templates(template_dir)
    assert len(templates) == 1

    result = stage_course_materials(
        template_path=templates[0][0],
        template=templates[0][1],
        project_root=project_root,
        kb_base_dir=kb_base_dir,
        rag_provider="milvus",
    )
    update_kb_config(kb_base_dir=kb_base_dir, results=[result], rag_provider="milvus")

    assert result.copied == ["lesson.pdf"]
    assert result.raw_document_count == 1
    assert result.needs_reindex is True
    assert (kb_base_dir / "演示课程资料" / "raw" / "lesson.pdf").exists()

    metadata = json.loads((kb_base_dir / "演示课程资料" / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["course_template_id"] == "demo_course"
    assert metadata["course_id"] == "DEMO101"
    assert metadata["raw_document_count"] == 1
    assert metadata["needs_reindex"] is True
    assert "lesson.pdf" in metadata["file_hashes"]

    config = json.loads((kb_base_dir / "kb_config.json").read_text(encoding="utf-8"))
    entry = config["knowledge_bases"]["演示课程资料"]
    assert entry["status"] == "needs_reindex"
    assert entry["needs_reindex"] is True
    assert entry["raw_document_count"] == 1


def test_sync_course_materials_is_idempotent_when_files_match(tmp_path: Path) -> None:
    project_root = tmp_path
    kb_base_dir = project_root / "data" / "knowledge_bases"
    material = project_root / "ppts" / "demo" / "lesson.pdf"
    material.parent.mkdir(parents=True)
    material.write_bytes(b"%PDF-1.4\nfake lesson\n")

    template_path = project_root / "data" / "course_templates" / "demo.json"
    template = {
        "id": "demo",
        "course_name": "演示课程",
        "source_materials": ["ppts/demo/lesson.pdf"],
    }

    first = stage_course_materials(
        template_path=template_path,
        template=template,
        project_root=project_root,
        kb_base_dir=kb_base_dir,
        rag_provider="milvus",
    )
    second = stage_course_materials(
        template_path=template_path,
        template=template,
        project_root=project_root,
        kb_base_dir=kb_base_dir,
        rag_provider="milvus",
    )

    assert first.copied == ["lesson.pdf"]
    assert second.copied == []
    assert second.skipped == ["lesson.pdf"]
    assert second.collisions == []


def test_sync_course_materials_keeps_reindex_when_marker_count_is_stale(tmp_path: Path) -> None:
    project_root = tmp_path
    kb_base_dir = project_root / "data" / "knowledge_bases"
    material_dir = project_root / "ppts" / "demo"
    material_dir.mkdir(parents=True)
    (material_dir / "lesson-1.pdf").write_bytes(b"%PDF-1.4\nlesson 1\n")
    (material_dir / "lesson-2.pdf").write_bytes(b"%PDF-1.4\nlesson 2\n")

    marker = kb_base_dir / "演示课程" / "milvus_storage" / "metadata.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({"document_count": 1}), encoding="utf-8")

    template = {
        "id": "demo",
        "course_name": "演示课程",
        "source_materials": [
            "ppts/demo/lesson-1.pdf",
            "ppts/demo/lesson-2.pdf",
        ],
    }

    first = stage_course_materials(
        template_path=project_root / "data" / "course_templates" / "demo.json",
        template=template,
        project_root=project_root,
        kb_base_dir=kb_base_dir,
        rag_provider="milvus",
    )
    second = stage_course_materials(
        template_path=project_root / "data" / "course_templates" / "demo.json",
        template=template,
        project_root=project_root,
        kb_base_dir=kb_base_dir,
        rag_provider="milvus",
    )

    assert first.raw_document_count == 2
    assert second.copied == []
    assert second.skipped == ["lesson-1.pdf", "lesson-2.pdf"]
    assert second.needs_reindex is True
