#!/usr/bin/env python
"""Validate guided-learning course template JSON files."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIRS = [
    ROOT / "data" / "course_templates",
]


def main() -> int:
    errors: list[str] = []
    seen_ids: set[str] = set()
    checked = 0
    for directory in TEMPLATE_DIRS:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            checked += 1
            validate_template(path, seen_ids, errors)
    if errors:
        print("[course-templates] validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"[course-templates] validated {checked} template(s).")
    return 0


def validate_template(path: Path, seen_ids: set[str], errors: list[str]) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{path}: invalid JSON: {exc}")
        return
    if not isinstance(payload, dict):
        errors.append(f"{path}: template must be a JSON object")
        return
    template_id = string_field(payload, "id")
    if not template_id:
        errors.append(f"{path}: missing id")
    elif template_id in seen_ids:
        errors.append(f"{path}: duplicate id {template_id}")
    else:
        seen_ids.add(template_id)
    for field in ("title", "course_name", "default_goal", "description"):
        if not string_field(payload, field):
            errors.append(f"{path}: missing {field}")
    for field in ("learning_outcomes", "assessment", "project_milestones"):
        if field in payload and not isinstance(payload[field], list):
            errors.append(f"{path}: {field} must be a list")
    nodes = payload.get("nodes", [])
    tasks = payload.get("tasks", [])
    if nodes and not isinstance(nodes, list):
        errors.append(f"{path}: nodes must be a list")
        nodes = []
    if tasks and not isinstance(tasks, list):
        errors.append(f"{path}: tasks must be a list")
        tasks = []
    node_ids = validate_nodes(path, nodes, errors)
    task_ids = validate_tasks(path, tasks, node_ids, errors)
    validate_demo_seed(path, payload.get("demo_seed"), task_ids, errors)


def validate_nodes(path: Path, nodes: Any, errors: list[str]) -> set[str]:
    node_ids: set[str] = set()
    if not isinstance(nodes, list):
        return node_ids
    for index, item in enumerate(nodes, start=1):
        if not isinstance(item, dict):
            errors.append(f"{path}: nodes[{index}] must be an object")
            continue
        node_id = string_field(item, "node_id")
        title = string_field(item, "title")
        if not node_id:
            errors.append(f"{path}: nodes[{index}] missing node_id")
        elif node_id in node_ids:
            errors.append(f"{path}: duplicate node_id {node_id}")
        else:
            node_ids.add(node_id)
        if not title:
            errors.append(f"{path}: nodes[{index}] missing title")
        prerequisites = item.get("prerequisites", [])
        if prerequisites and not isinstance(prerequisites, list):
            errors.append(f"{path}: nodes[{index}].prerequisites must be a list")
    for index, item in enumerate(nodes, start=1):
        if not isinstance(item, dict):
            continue
        for prerequisite in item.get("prerequisites", []) if isinstance(item.get("prerequisites", []), list) else []:
            if str(prerequisite) not in node_ids:
                errors.append(f"{path}: nodes[{index}] references unknown prerequisite {prerequisite}")
    return node_ids


def validate_tasks(path: Path, tasks: Any, node_ids: set[str], errors: list[str]) -> set[str]:
    task_ids: set[str] = set()
    if not isinstance(tasks, list):
        return task_ids
    for index, item in enumerate(tasks, start=1):
        if not isinstance(item, dict):
            errors.append(f"{path}: tasks[{index}] must be an object")
            continue
        task_id = string_field(item, "task_id")
        node_id = string_field(item, "node_id")
        if not task_id:
            errors.append(f"{path}: tasks[{index}] missing task_id")
        elif task_id in task_ids:
            errors.append(f"{path}: duplicate task_id {task_id}")
        else:
            task_ids.add(task_id)
        if node_ids and node_id not in node_ids:
            errors.append(f"{path}: tasks[{index}] references unknown node_id {node_id}")
        for field in ("title", "instruction"):
            if not string_field(item, field):
                errors.append(f"{path}: tasks[{index}] missing {field}")
    return task_ids


def validate_demo_seed(path: Path, demo_seed: Any, task_ids: set[str], errors: list[str]) -> None:
    if demo_seed in (None, {}):
        return
    if not isinstance(demo_seed, dict):
        errors.append(f"{path}: demo_seed must be an object")
        return
    task_chain = demo_seed.get("task_chain", [])
    if task_chain and not isinstance(task_chain, list):
        errors.append(f"{path}: demo_seed.task_chain must be a list")
        return
    for task_id in task_chain:
        if task_ids and str(task_id) not in task_ids:
            errors.append(f"{path}: demo_seed references unknown task {task_id}")
    validate_demo_seed_artifacts(path, demo_seed.get("sample_artifacts"), task_ids, errors)


def validate_demo_seed_artifacts(path: Path, artifacts: Any, task_ids: set[str], errors: list[str]) -> None:
    if artifacts in (None, []):
        errors.append(f"{path}: demo_seed.sample_artifacts should include stable recording fallback assets")
        return
    if not isinstance(artifacts, list):
        errors.append(f"{path}: demo_seed.sample_artifacts must be a list")
        return
    structured_detail_fields = {
        "diagram_nodes",
        "video_beats",
        "quiz_items",
        "key_takeaways",
        "evidence_points",
        "agent_route",
        "report_sections",
        "sample_prescription",
        "code_snippet",
        "latex_focus",
    }
    for index, item in enumerate(artifacts, start=1):
        if not isinstance(item, dict):
            errors.append(f"{path}: demo_seed.sample_artifacts[{index}] must be an object")
            continue
        task_id = string_field(item, "task_id")
        if task_id and task_ids and task_id not in task_ids:
            errors.append(f"{path}: demo_seed.sample_artifacts[{index}] references unknown task {task_id}")
        for field in ("title", "preview", "demo_action", "talking_point"):
            if not string_field(item, field):
                errors.append(f"{path}: demo_seed.sample_artifacts[{index}] missing {field}")
        if not any(item.get(field) not in (None, "", [], {}) for field in structured_detail_fields):
            errors.append(
                f"{path}: demo_seed.sample_artifacts[{index}] should include at least one structured detail field"
            )


def string_field(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    return str(value).strip() if value is not None else ""


if __name__ == "__main__":
    raise SystemExit(main())
