#!/usr/bin/env python
"""Export a lightweight SparkWeave competition submission package."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
from typing import Iterable

from export_demo_materials import (
    build_deck_html,
    build_deck_outline,
    build_defense_qa,
    build_index as build_demo_index,
    build_recording_script,
)


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "dist" / "competition_package"

DOCS = [
    ("README.md", "project-readme.md"),
    ("docs/README.md", "docs-index.md"),
    ("docs/architecture.md", "architecture.md"),
    ("docs/capabilities.md", "capabilities.md"),
    ("docs/competition-demo-runbook.md", "competition-demo-runbook.md"),
    ("docs/competition-roadmap.md", "competition-roadmap.md"),
    ("docs/demo-quickstart.md", "demo-quickstart.md"),
    ("docs/demo-course-templates.md", "demo-course-templates.md"),
    ("docs/demo-script-profile-guide-loop.md", "demo-script-profile-guide-loop.md"),
    ("docs/guided-learning.md", "guided-learning.md"),
    ("docs/learner-profile-design.md", "learner-profile-design.md"),
    ("docs/ai-coding-statement.md", "ai-coding-statement.md"),
    ("docs/configuration.md", "configuration.md"),
    ("docs/getting-started.md", "getting-started.md"),
]

RUNTIME_FILES = [
    (".env.example", ".env.example"),
    ("pyproject.toml", "pyproject.toml"),
    ("requirements.txt", "requirements.txt"),
    ("requirements/server.txt", "requirements/server.txt"),
    ("requirements/dev.txt", "requirements/dev.txt"),
    ("requirements/math-animator.txt", "requirements/math-animator.txt"),
    ("requirements/sparkbot.txt", "requirements/sparkbot.txt"),
    ("scripts/start_web.py", "scripts/start_web.py"),
    ("scripts/check_install.py", "scripts/check_install.py"),
    ("scripts/check_course_templates.py", "scripts/check_course_templates.py"),
    ("scripts/check_competition_readiness.py", "scripts/check_competition_readiness.py"),
    ("scripts/export_competition_package.py", "scripts/export_competition_package.py"),
    ("scripts/export_demo_materials.py", "scripts/export_demo_materials.py"),
]

ASSETS = [
    ("assets/logo-ver2.png", "logo-ver2.png"),
    ("assets/architecture.svg", "architecture.svg"),
    ("docs/assets/guided-learning-loop.svg", "guided-learning-loop.svg"),
]

SCREENSHOT_PATTERNS = [
    "screenshots-refined-chat.png",
    "screenshots-simplified-guide.png",
    "screenshots-simplified-final-knowledge.png",
    "screenshots-simplified-final-question.png",
    "screenshots-simplified-final-vision.png",
    "screenshots-simplified-notebook.png",
    "screenshots-finalcheck-agents.png",
    "screenshots-simplified-final-settings.png",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output directory. Defaults to dist/competition_package.",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not remove the output directory before exporting.",
    )
    args = parser.parse_args()

    output = prepare_output(args.output, clean=not args.no_clean)
    copied: list[str] = []
    missing: list[str] = []

    copy_many(DOCS, output / "docs", copied, missing)
    copy_many(RUNTIME_FILES, output / "runtime", copied, missing)
    copy_many(ASSETS, output / "assets", copied, missing)
    copy_course_templates(output / "course_templates", copied, missing)
    copy_screenshots(output / "screenshots", copied, missing)
    export_demo_materials(output / "demo_materials", copied, missing)

    manifest = build_manifest(output, copied, missing)
    (output / "README.md").write_text(manifest, encoding="utf-8")
    (output / "submission_manifest.md").write_text(manifest, encoding="utf-8")

    print(f"[competition-package] exported to {output}")
    print(f"[competition-package] copied {len(copied)} file(s), missing {len(missing)} file(s).")
    if missing:
        print("[competition-package] missing files:")
        for item in missing:
            print(f"- {item}")
    return 0


def prepare_output(output: Path, *, clean: bool) -> Path:
    output = output if output.is_absolute() else ROOT / output
    resolved = output.resolve()
    allowed_root = (ROOT / "dist").resolve()
    if clean and resolved.exists():
        if resolved == allowed_root or allowed_root not in resolved.parents:
            raise RuntimeError(f"Refuse to clean output outside project dist/: {resolved}")
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def copy_many(paths: Iterable[tuple[str, str]], target_dir: Path, copied: list[str], missing: list[str]) -> None:
    for relative, target_name in paths:
        source = ROOT / relative
        if not source.exists():
            missing.append(relative)
            continue
        target = target_dir / target_name
        copy_file(source, target, copied)


def copy_course_templates(target_dir: Path, copied: list[str], missing: list[str]) -> None:
    template_dir = ROOT / "data" / "course_templates"
    if not template_dir.exists():
        missing.append("data/course_templates/*.json")
        return
    for source in sorted(template_dir.glob("*.json")):
        copy_file(source, target_dir / source.name, copied)


def copy_screenshots(target_dir: Path, copied: list[str], missing: list[str]) -> None:
    for name in SCREENSHOT_PATTERNS:
        source = ROOT / "web" / name
        if not source.exists():
            missing.append(f"web/{name}")
            continue
        copy_file(source, target_dir / name, copied)


def export_demo_materials(target_dir: Path, copied: list[str], missing: list[str]) -> None:
    template_path = ROOT / "data" / "course_templates" / "ai_learning_agents_systems.json"
    if not template_path.exists():
        missing.append("data/course_templates/ai_learning_agents_systems.json")
        return
    template = json.loads(template_path.read_text(encoding="utf-8"))
    target_dir.mkdir(parents=True, exist_ok=True)
    materials = {
        "README.md": build_demo_index(template, target_dir),
        "sparkweave-demo-deck-outline.md": build_deck_outline(template),
        "sparkweave-demo-deck.html": build_deck_html(template),
        "sparkweave-7min-recording-script.md": build_recording_script(template),
        "sparkweave-defense-qa.md": build_defense_qa(template),
    }
    for name, content in materials.items():
        target = target_dir / name
        target.write_text(content, encoding="utf-8")
        copied.append(f"demo_materials/{name}")


def copy_file(source: Path, target: Path, copied: list[str]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    copied.append(str(source.relative_to(ROOT)).replace("\\", "/"))


def build_manifest(output: Path, copied: list[str], missing: list[str]) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    course_template_count = len([item for item in copied if item.startswith("data/course_templates/")])
    screenshot_count = len([item for item in copied if item.startswith("web/screenshots")])
    demo_material_count = len([item for item in copied if item.startswith("demo_materials/")])
    lines = [
        "# SparkWeave 比赛提交包索引",
        "",
        f"- 生成时间：{generated_at}",
        f"- 输出目录：`{output}`",
        f"- 文档数量：{len([item for item in copied if item.endswith('.md')])}",
        f"- 课程模板：{course_template_count}",
        f"- 页面截图：{screenshot_count}",
        f"- 离线演示材料：{demo_material_count}",
        "",
        "## 文件夹说明",
        "",
        "- `docs/`：项目说明、架构、能力、导学、学习画像、比赛路线图、演示 Runbook 和 AI Coding 说明。",
        "- `course_templates/`：可复现的完整高校课程样例，适合录屏和答辩现场演示。",
        "- `demo_materials/`：离线生成的 PPT 骨架、可打印演示页、7 分钟录屏讲稿和答辩问答预案。",
        "- `screenshots/`：当前前端关键页面截图，可直接放入 PPT 或项目展示页。",
        "- `assets/`：Logo、系统架构图和导学闭环图。",
        "- `runtime/`：环境样例、依赖清单、启动脚本和安装检查脚本。",
        "",
        "## 赛题提交物映射",
        "",
        "| 提交物 | 本包对应材料 |",
        "| --- | --- |",
        "| 演示 PPT | `demo_materials/sparkweave-demo-deck-outline.md`、`demo_materials/sparkweave-demo-deck.html`、`docs/competition-demo-runbook.md`、`screenshots/` |",
        "| 可运行源码与配置 | GitHub 仓库源码、`runtime/.env.example`、`runtime/requirements*.txt`、`runtime/scripts/start_web.py` |",
        "| 7 分钟演示视频 | `demo_materials/sparkweave-7min-recording-script.md`、`docs/competition-demo-runbook.md` 的分镜和兜底动作 |",
        "| 完整高校课程 | `course_templates/` 中的 ROS、高数、大模型教育智能体课程模板 |",
        "| 多智能体资源生成 | `docs/capabilities.md`、`docs/guided-learning.md`、`docs/architecture.md` |",
        "| 学习效果评估 | `docs/guided-learning.md`、`docs/learner-profile-design.md`、课程产出包 Markdown 导出 |",
        "| 答辩问答 | `demo_materials/sparkweave-defense-qa.md`、课程产出包中的答辩问答预案 |",
        "| AI Coding 说明 | `docs/ai-coding-statement.md` |",
        "",
        "## 建议使用顺序",
        "",
        "1. 先按 `docs/getting-started.md` 和 `runtime/scripts/check_install.py` 确认环境。",
        "2. 先用 `demo_materials/` 离线材料搭 PPT、视频脚本和答辩问答骨架。",
        "3. 运行 Web 后打开 `/guide`，优先选择“大模型教育智能体系统开发”赛题主线课程。",
        "4. 按 `docs/competition-demo-runbook.md` 录制 7 分钟演示视频。",
        "5. 使用导学页的课程产出包和学习报告 Markdown 下载按钮，把真实 session 证据补入 PPT 和提交文档。",
        "6. 赛前再次运行 `python scripts/check_course_templates.py`、`cd web && npm run build`。",
    ]
    if missing:
        lines.extend(["", "## 缺失文件", ""])
        lines.extend(f"- `{item}`" for item in missing)
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
