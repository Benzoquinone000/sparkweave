#!/usr/bin/env python
"""Run a lightweight SparkWeave competition readiness check."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import unquote
import zipfile


ROOT = Path(__file__).resolve().parent.parent

REQUIRED_DOCS = [
    "README.md",
    "docs/architecture.md",
    "docs/capabilities.md",
    "docs/competition-demo-runbook.md",
    "docs/competition-roadmap.md",
    "docs/demo-quickstart.md",
    "docs/guided-learning.md",
    "docs/learner-profile-design.md",
    "docs/iflytek-integration.md",
    "docs/ai-coding-statement.md",
]

REQUIRED_RUNTIME_FILES = [
    ".env.example",
    "requirements.txt",
    "requirements/server.txt",
    "requirements/math-animator.txt",
    "scripts/start_web.py",
    "scripts/check_install.py",
    "scripts/check_release_safety.py",
    "scripts/check_competition_readiness.py",
    "scripts/render_competition_summary.py",
    "scripts/verify_competition_package.py",
    "scripts/export_demo_materials.py",
    "scripts/export_competition_package.py",
]

REQUIRED_ASSETS = [
    "assets/logo-ver2.png",
    "assets/architecture.svg",
    "docs/assets/guided-learning-loop.svg",
    "docs/assets/agent-collaboration-blueprint.svg",
]

REQUIRED_SCREENSHOTS = [
    "web/screenshots-refined-chat.png",
    "web/screenshots-simplified-guide.png",
    "web/screenshots-simplified-final-knowledge.png",
    "web/screenshots-simplified-final-question.png",
    "web/screenshots-simplified-final-vision.png",
    "web/screenshots-simplified-notebook.png",
    "web/screenshots-finalcheck-agents.png",
    "web/screenshots-simplified-final-settings.png",
]

REQUIRED_COURSE_TEMPLATES = [
    "data/course_templates/ai_learning_agents_systems.json",
    "data/course_templates/higher_math_limits_derivatives.json",
    "data/course_templates/robotics_ros_foundations.json",
]

GENERATED_DEMO_FILES = [
    "README.md",
    "sparkweave-demo-deck-outline.md",
    "sparkweave-demo-deck.html",
    "sparkweave-7min-recording-script.md",
    "sparkweave-agent-collaboration-blueprint.md",
    "sparkweave-demo-fallback-assets.md",
    "sparkweave-defense-qa.md",
    "sparkweave-competition-scorecard.md",
    "sparkweave-evaluator-one-pager.md",
    "sparkweave-final-pitch-checklist.md",
]


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "ok": self.ok,
            "detail": self.detail,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format. Defaults to text.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the machine-readable JSON report.",
    )
    args = parser.parse_args()

    report = build_report()
    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text_report(report)
    return 0 if report["success"] else 1


def build_report() -> dict[str, object]:
    checks: list[Check] = []
    checks.extend(check_paths("Docs", REQUIRED_DOCS))
    checks.extend(check_paths("Runtime", REQUIRED_RUNTIME_FILES))
    checks.extend(check_paths("Assets", REQUIRED_ASSETS))
    checks.extend(check_paths("Screenshots", REQUIRED_SCREENSHOTS))
    checks.extend(check_paths("Course templates", REQUIRED_COURSE_TEMPLATES))
    checks.append(run_project_script("Release safety", "check_release_safety.py"))
    checks.append(run_project_script("Course template schema", "check_course_templates.py"))
    checks.extend(check_runtime_collaboration_route())
    checks.extend(check_external_video_learning_loop())
    checks.extend(check_effect_assessment_chain())
    checks.extend(check_competition_proof_chain())
    checks.extend(check_user_facing_settings_diagnostics())
    checks.extend(check_user_facing_knowledge_progress())
    checks.extend(check_user_facing_chat_trace())
    checks.extend(check_generated_exports())

    failed = [item for item in checks if not item.ok]
    return {
        "success": not failed,
        "total_count": len(checks),
        "ready_count": len(checks) - len(failed),
        "failed_count": len(failed),
        "summary": (
            "All required competition materials are ready."
            if not failed
            else f"{len(failed)} check(s) need attention before submission."
        ),
        "checks": [item.to_dict() for item in checks],
    }


def print_text_report(report: dict[str, object]) -> None:
    checks = [item for item in report.get("checks", []) if isinstance(item, dict)]
    print("\nSparkWeave competition readiness")
    print("=" * 40)
    for item in checks:
        ok = bool(item.get("ok"))
        mark = "ok" if ok else "fail"
        detail = str(item.get("detail") or "")
        suffix = f" - {detail}" if detail else ""
        print(f"[{mark}] {item.get('name')}{suffix}")
    print("=" * 40)
    print(str(report.get("summary") or ""))


def check_paths(group: str, paths: list[str]) -> list[Check]:
    checks: list[Check] = []
    for relative in paths:
        path = ROOT / relative
        checks.append(Check(f"{group}: {relative}", path.exists(), "missing" if not path.exists() else ""))
    return checks


def run_project_script(name: str, script_name: str, *args: str) -> Check:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script_name), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    if result.returncode == 0:
        return Check(name, True, compact_output(result.stdout))
    return Check(name, False, compact_output(result.stderr or result.stdout))


def check_runtime_collaboration_route() -> list[Check]:
    expectations = [
        (
            "Runtime collaboration route: backend emitter",
            "sparkweave/graphs/chat.py",
            ["SPECIALIST_COLLABORATION_ROUTES", '"collaboration_route_version": 1', '"collaboration_route"'],
        ),
        (
            "Runtime collaboration route: frontend viewer",
            "web/src/components/chat/AgentCollaborationPanel.tsx",
            ["findStructuredRoute", "collaboration_route", "agent_chain"],
        ),
        (
            "Runtime collaboration route: test coverage",
            "tests/ng/test_chat_graph.py",
            ["collaboration_route_version", "collaboration_route"],
        ),
    ]
    checks: list[Check] = []
    for name, relative, needles in expectations:
        path = ROOT / relative
        if not path.exists():
            checks.append(Check(name, False, f"missing {relative}"))
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            checks.append(Check(name, False, f"not utf-8 text: {exc}"))
            continue
        missing = [needle for needle in needles if needle not in content]
        checks.append(Check(name, not missing, "" if not missing else f"missing {', '.join(missing)}"))
    return checks


def check_external_video_learning_loop() -> list[Check]:
    expectations = [
        (
            "External video loop: search service",
            "sparkweave/services/video_search.py",
            ["recommend_learning_videos", "watch_plan", "reflection_prompt", "fallback_search"],
        ),
        (
            "External video loop: chat handoff",
            "sparkweave/graphs/chat.py",
            ["external_video_search", "_looks_like_external_video_request", "_run_external_video_search"],
        ),
        (
            "External video loop: viewer evidence",
            "web/src/components/results/ExternalVideoViewer.tsx",
            ["external-video-viewer", "external-video-watch-plan", "external-video-mark-viewed", "appendLearnerEvidence"],
        ),
        (
            "External video loop: test coverage",
            "tests/services/test_video_search.py",
            ["watch_plan", "reflection_prompt", "fallback_search"],
        ),
    ]
    checks: list[Check] = []
    for name, relative, needles in expectations:
        path = ROOT / relative
        if not path.exists():
            checks.append(Check(name, False, f"missing {relative}"))
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            checks.append(Check(name, False, f"not utf-8 text: {exc}"))
            continue
        missing = [needle for needle in needles if needle not in content]
        checks.append(Check(name, not missing, "" if not missing else f"missing {', '.join(missing)}"))
    return checks


def check_effect_assessment_chain() -> list[Check]:
    expectations = [
        (
            "Effect assessment chain: backend report",
            "sparkweave/services/guide_v2.py",
            ["assessment_chain", "观察证据", "定位瓶颈", "调整策略"],
        ),
        (
            "Effect assessment chain: frontend card",
            "web/src/pages/GuidePage.tsx",
            ["EffectAssessmentCard", "guide-effect-assessment-chain", "评估依据"],
        ),
        (
            "Effect assessment chain: test coverage",
            "tests/services/test_guide_v2.py",
            ["assessment_chain", "评估链路"],
        ),
    ]
    checks: list[Check] = []
    for name, relative, needles in expectations:
        path = ROOT / relative
        if not path.exists():
            checks.append(Check(name, False, f"missing {relative}"))
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            checks.append(Check(name, False, f"not utf-8 text: {exc}"))
            continue
        missing = [needle for needle in needles if needle not in content]
        checks.append(Check(name, not missing, "" if not missing else f"missing {', '.join(missing)}"))
    return checks


def check_competition_proof_chain() -> list[Check]:
    expectations = [
        (
            "Competition proof chain: backend package",
            "sparkweave/services/guide_v2.py",
            ["proof_chain", "功能证据", "现场动作", "答辩讲法"],
        ),
        (
            "Competition proof chain: frontend card",
            "web/src/pages/GuidePage.tsx",
            ["guide-competition-proof-chain", "proofChain", "证明"],
        ),
        (
            "Competition proof chain: test coverage",
            "tests/services/test_guide_v2.py",
            ["proof_chain", "三步证明链"],
        ),
    ]
    checks: list[Check] = []
    for name, relative, needles in expectations:
        path = ROOT / relative
        if not path.exists():
            checks.append(Check(name, False, f"missing {relative}"))
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            checks.append(Check(name, False, f"not utf-8 text: {exc}"))
            continue
        missing = [needle for needle in needles if needle not in content]
        checks.append(Check(name, not missing, "" if not missing else f"missing {', '.join(missing)}"))
    return checks


def check_user_facing_settings_diagnostics() -> list[Check]:
    expectations = [
        (
            "User-facing diagnostics: settings status strip",
            "web/src/pages/SettingsPage.tsx",
            [
                "friendlyServiceError",
                "settings-status-strip",
                "signature",
                "upstream",
                "ServiceStatusStrip",
            ],
        ),
        (
            "User-facing diagnostics: test coverage",
            "web/tests/e2e/workbench-smoke.spec.ts",
            [
                "settings-status-strip",
                "HMAC secret key does not match",
                "The upstream server is timing out",
                "not.toContainText",
            ],
        ),
    ]
    checks: list[Check] = []
    for name, relative, needles in expectations:
        path = ROOT / relative
        if not path.exists():
            checks.append(Check(name, False, f"missing {relative}"))
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            checks.append(Check(name, False, f"not utf-8 text: {exc}"))
            continue
        missing = [needle for needle in needles if needle not in content]
        checks.append(Check(name, not missing, "" if not missing else f"missing {', '.join(missing)}"))
    return checks


def check_user_facing_knowledge_progress() -> list[Check]:
    expectations = [
        (
            "User-facing knowledge progress: milestone view",
            "web/src/pages/KnowledgePage.tsx",
            [
                "knowledge-task-milestones",
                "knowledge-task-log-details",
                "summarizeKnowledgeTaskLogs",
                "formatKnowledgeLogLine",
                "withLegacyText",
            ],
        ),
        (
            "User-facing knowledge progress: test coverage",
            "web/tests/e2e/workbench-smoke.spec.ts",
            [
                "knowledge-task-milestones",
                "knowledge-task-log-details",
                "knowledge-task-logs",
                "not.toContainText",
            ],
        ),
    ]
    checks: list[Check] = []
    for name, relative, needles in expectations:
        path = ROOT / relative
        if not path.exists():
            checks.append(Check(name, False, f"missing {relative}"))
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            checks.append(Check(name, False, f"not utf-8 text: {exc}"))
            continue
        missing = [needle for needle in needles if needle not in content]
        checks.append(Check(name, not missing, "" if not missing else f"missing {', '.join(missing)}"))
    return checks


def check_user_facing_chat_trace() -> list[Check]:
    expectations = [
        (
            "User-facing chat trace: collaboration viewer",
            "web/src/components/chat/AgentCollaborationPanel.tsx",
            [
                "协作明细",
                "智能体协作",
                "meaningfulContent",
                "readableEvents",
                "profile_guided",
            ],
        ),
        (
            "User-facing chat trace: final-answer test coverage",
            "web/tests/e2e/workbench-smoke.spec.ts",
            [
                "stage_start",
                "Thinking...",
                "Writing final polish",
                "· thinking",
                "not.toContainText",
            ],
        ),
    ]
    checks: list[Check] = []
    for name, relative, needles in expectations:
        path = ROOT / relative
        if not path.exists():
            checks.append(Check(name, False, f"missing {relative}"))
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            checks.append(Check(name, False, f"not utf-8 text: {exc}"))
            continue
        missing = [needle for needle in needles if needle not in content]
        checks.append(Check(name, not missing, "" if not missing else f"missing {', '.join(missing)}"))
    return checks


def check_generated_exports() -> list[Check]:
    checks: list[Check] = []
    with tempfile.TemporaryDirectory(prefix="sparkweave-ready-") as tmp:
        tmpdir = Path(tmp)
        demo_dir = tmpdir / "demo_materials"
        package_dir = tmpdir / "competition_package"
        archive_path = tmpdir / "sparkweave_competition_package.zip"

        checks.append(
            run_project_script(
                "Offline demo material export",
                "export_demo_materials.py",
                "--output",
                str(demo_dir),
            )
        )
        checks.extend(check_generated_files("Generated demo", demo_dir, GENERATED_DEMO_FILES))
        checks.extend(
            check_generated_content(
                "Generated demo content",
                demo_dir,
                [
                    ("sparkweave-demo-deck.html", "SparkWeave 演示页"),
                    ("sparkweave-demo-deck-outline.md", "SparkWeave 演示 PPT 骨架"),
                    ("sparkweave-7min-recording-script.md", "SparkWeave 7 分钟录屏讲稿"),
                    ("sparkweave-agent-collaboration-blueprint.md", "SparkWeave 多智能体协作蓝图"),
                    ("sparkweave-demo-fallback-assets.md", "SparkWeave 稳定演示兜底素材"),
                    ("sparkweave-defense-qa.md", "SparkWeave 答辩问答预案"),
                    ("sparkweave-competition-scorecard.md", "SparkWeave 赛题评分点证据表"),
                    ("sparkweave-evaluator-one-pager.md", "SparkWeave 评委一页说明"),
                    ("sparkweave-final-pitch-checklist.md", "SparkWeave 最终答辩材料清单"),
                ],
            )
        )
        checks.append(
            check_html_local_links(
                "Generated demo links: sparkweave-demo-deck.html",
                demo_dir / "sparkweave-demo-deck.html",
            )
        )

        checks.append(
            run_project_script(
                "Competition package export",
                "export_competition_package.py",
                "--output",
                str(package_dir),
                "--archive",
                str(archive_path),
            )
        )
        checks.append(
            Check(
                "Competition package archive",
                archive_path.exists() and archive_path.stat().st_size > 0,
                "missing or empty archive" if not archive_path.exists() or archive_path.stat().st_size <= 0 else "",
            )
        )
        checks.extend(
            check_archive_entries(
                archive_path,
                [
                    "competition_package/index.html",
                    "competition_package/checksums.sha256",
                    "competition_package/submission_manifest.md",
                    "competition_package/demo_materials/sparkweave-demo-deck.html",
                    "competition_package/demo_materials/sparkweave-competition-scorecard.md",
                    "competition_package/demo_materials/sparkweave-7min-recording-script.md",
                    "competition_package/assets/architecture.svg",
                    "competition_package/runtime/scripts/start_web.py",
                    "competition_package/screenshots/screenshots-simplified-guide.png",
                ],
            )
        )
        checks.append(check_archive_safety(archive_path))
        checks.extend(
            check_generated_files(
                "Generated package",
                package_dir,
                [
                    "index.html",
                    "checksums.sha256",
                    "README.md",
                    "submission_manifest.md",
                    "demo_materials/sparkweave-demo-deck.html",
                    "demo_materials/sparkweave-agent-collaboration-blueprint.md",
                    "demo_materials/sparkweave-demo-fallback-assets.md",
                    "demo_materials/sparkweave-competition-scorecard.md",
                    "demo_materials/sparkweave-evaluator-one-pager.md",
                    "demo_materials/sparkweave-final-pitch-checklist.md",
                    "assets/agent-collaboration-blueprint.svg",
                    "course_templates/ai_learning_agents_systems.json",
                    "runtime/scripts/check_competition_readiness.py",
                    "runtime/scripts/check_release_safety.py",
                    "runtime/scripts/render_competition_summary.py",
                    "runtime/scripts/verify_competition_package.py",
                    "runtime/scripts/start_web.py",
                    "screenshots/screenshots-simplified-guide.png",
                ],
            )
        )
        checks.extend(
            check_generated_content(
                "Generated package content",
                package_dir,
                [
                    ("index.html", "SparkWeave 星火织学提交包"),
                    ("checksums.sha256", "index.html"),
                    ("submission_manifest.md", "SparkWeave 比赛提交包索引"),
                    ("docs/iflytek-integration.md", "科大讯飞能力接入说明"),
                    ("demo_materials/sparkweave-demo-deck.html", "SparkWeave 演示页"),
                    ("demo_materials/sparkweave-agent-collaboration-blueprint.md", "SparkWeave 多智能体协作蓝图"),
                    ("demo_materials/sparkweave-demo-fallback-assets.md", "SparkWeave 稳定演示兜底素材"),
                    ("demo_materials/sparkweave-competition-scorecard.md", "SparkWeave 赛题评分点证据表"),
                    ("demo_materials/sparkweave-evaluator-one-pager.md", "SparkWeave 评委一页说明"),
                    ("demo_materials/sparkweave-final-pitch-checklist.md", "SparkWeave 最终答辩材料清单"),
                    ("docs/demo-quickstart.md", "演示者 5 分钟入口"),
                ],
            )
        )
        checks.append(check_html_local_links("Generated package links: index.html", package_dir / "index.html"))
        checks.append(
            check_html_local_links(
                "Generated package links: demo_materials/sparkweave-demo-deck.html",
                package_dir / "demo_materials" / "sparkweave-demo-deck.html",
            )
        )
        checks.append(check_package_checksums(package_dir))
    return checks


def check_generated_files(group: str, root: Path, relative_paths: list[str]) -> list[Check]:
    return [
        Check(f"{group}: {relative}", (root / relative).exists(), "missing after export" if not (root / relative).exists() else "")
        for relative in relative_paths
    ]


def check_archive_entries(archive_path: Path, expected_entries: list[str]) -> list[Check]:
    checks: list[Check] = []
    if not archive_path.exists():
        return [Check("Competition archive content", False, "archive missing")]
    try:
        with zipfile.ZipFile(archive_path) as archive:
            entries = set(archive.namelist())
    except zipfile.BadZipFile as exc:
        return [Check("Competition archive content", False, f"bad zip file: {exc}")]

    for entry in expected_entries:
        checks.append(
            Check(
                f"Competition archive content: {entry}",
                entry in entries,
                "missing from archive" if entry not in entries else "",
            )
        )
    return checks


def check_package_checksums(package_dir: Path) -> Check:
    checksum_path = package_dir / "checksums.sha256"
    if not checksum_path.exists():
        return Check("Generated package checksums", False, "missing checksums.sha256")
    try:
        lines = [line.strip() for line in checksum_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except UnicodeDecodeError as exc:
        return Check("Generated package checksums", False, f"not utf-8 text: {exc}")

    expected_files = {
        path.relative_to(package_dir).as_posix()
        for path in package_dir.rglob("*")
        if path.is_file() and path != checksum_path
    }
    recorded: dict[str, str] = {}
    for line in lines:
        try:
            digest, relative = line.split("  ", 1)
        except ValueError:
            return Check("Generated package checksums", False, f"invalid checksum line: {line[:80]}")
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest.lower()):
            return Check("Generated package checksums", False, f"invalid sha256 digest for {relative}")
        recorded[relative] = digest.lower()

    missing = sorted(expected_files - recorded.keys())
    extra = sorted(recorded.keys() - expected_files)
    if missing:
        return Check("Generated package checksums", False, "missing checksum for " + ", ".join(missing[:5]))
    if extra:
        return Check("Generated package checksums", False, "checksum references missing file " + ", ".join(extra[:5]))

    mismatched: list[str] = []
    for relative, expected_digest in recorded.items():
        if sha256_file(package_dir / relative) != expected_digest:
            mismatched.append(relative)
    if mismatched:
        return Check("Generated package checksums", False, "checksum mismatch: " + ", ".join(mismatched[:5]))
    return Check("Generated package checksums", True, f"{len(recorded)} file checksum(s) verified")


def check_archive_safety(archive_path: Path) -> Check:
    if not archive_path.exists():
        return Check("Competition archive safety", False, "archive missing")
    try:
        with zipfile.ZipFile(archive_path) as archive:
            entries = archive.namelist()
    except zipfile.BadZipFile as exc:
        return Check("Competition archive safety", False, f"bad zip file: {exc}")

    forbidden_files = {
        ".env",
        ".env.local",
        ".env.development",
        ".env.production",
        ".secrets.baseline",
    }
    forbidden_dirs = {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        "__pycache__",
        "node_modules",
        "data/user",
        "data/memory",
        "web/dist",
    }
    problems: list[str] = []

    for entry in entries:
        normalized = entry.replace("\\", "/").strip()
        parts = [part for part in normalized.split("/") if part]
        if not normalized or normalized.startswith("/") or (parts and ":" in parts[0]) or ".." in parts:
            problems.append(entry)
            continue
        if not normalized.startswith("competition_package/"):
            problems.append(entry)
            continue
        if parts and parts[-1] in forbidden_files:
            problems.append(entry)
            continue
        joined = "/".join(parts)
        wrapped = f"/{joined}/"
        if any(f"/{forbidden}/" in wrapped for forbidden in forbidden_dirs):
            problems.append(entry)

    if problems:
        return Check("Competition archive safety", False, "unsafe entries: " + ", ".join(problems[:5]))
    return Check("Competition archive safety", True, f"{len(entries)} archive entrie(s) checked")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_generated_content(group: str, root: Path, expectations: list[tuple[str, str]]) -> list[Check]:
    checks: list[Check] = []
    for relative, needle in expectations:
        path = root / relative
        if not path.exists():
            checks.append(Check(f"{group}: {relative}", False, "missing after export"))
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            checks.append(Check(f"{group}: {relative}", False, f"not utf-8 text: {exc}"))
            continue
        checks.append(
            Check(
                f"{group}: {relative}",
                needle in content,
                "" if needle in content else f"missing marker {needle!r}",
            )
        )
    return checks


class LocalLinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in {"href", "src", "poster"} and value:
                self.links.append(value)


def check_html_local_links(name: str, html_path: Path) -> Check:
    if not html_path.exists():
        return Check(name, False, "missing html file")
    try:
        content = html_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return Check(name, False, f"not utf-8 text: {exc}")

    collector = LocalLinkCollector()
    collector.feed(content)
    missing: list[str] = []
    for raw_link in collector.links:
        link = normalize_local_link(raw_link)
        if not link:
            continue
        target = (html_path.parent / link).resolve()
        if not target.exists():
            missing.append(raw_link)

    if missing:
        return Check(name, False, "missing local links: " + ", ".join(missing[:5]))
    return Check(name, True, f"{len(collector.links)} local link(s) checked")


def normalize_local_link(value: str) -> str:
    link = value.strip()
    lowered = link.lower()
    if (
        not link
        or link.startswith("#")
        or lowered.startswith(("http://", "https://", "mailto:", "tel:", "javascript:", "data:"))
    ):
        return ""
    link = link.split("#", 1)[0].split("?", 1)[0]
    return unquote(link)


def compact_output(value: str) -> str:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if not lines:
        return ""
    return lines[-1][:180]


if __name__ == "__main__":
    raise SystemExit(main())
