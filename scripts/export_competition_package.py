#!/usr/bin/env python
"""Export a lightweight SparkWeave competition submission package."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
from html import escape
import json
from pathlib import Path
import shutil
from typing import Iterable

from export_demo_materials import (
    DEFAULT_TEMPLATE_ID,
    build_agent_collaboration_blueprint,
    build_deck_html,
    build_deck_outline,
    build_competition_scorecard,
    build_defense_qa,
    build_demo_fallback_assets,
    build_evaluator_one_pager,
    build_final_pitch_checklist,
    build_index as build_demo_index,
    build_learning_effect_demo_summary,
    build_recording_script,
)


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "dist" / "competition_package"
DEFAULT_ARCHIVE = ROOT / "dist" / "sparkweave_competition_package.zip"

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
    ("docs/iflytek-integration.md", "iflytek-integration.md"),
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
    ("scripts/check_release_safety.py", "scripts/check_release_safety.py"),
    ("scripts/check_competition_readiness.py", "scripts/check_competition_readiness.py"),
    ("scripts/render_competition_summary.py", "scripts/render_competition_summary.py"),
    ("scripts/verify_competition_package.py", "scripts/verify_competition_package.py"),
    ("scripts/export_competition_package.py", "scripts/export_competition_package.py"),
    ("scripts/export_demo_materials.py", "scripts/export_demo_materials.py"),
]

ASSETS = [
    ("assets/logo-ver2.png", "logo-ver2.png"),
    ("assets/architecture.svg", "architecture.svg"),
    ("docs/assets/guided-learning-loop.svg", "guided-learning-loop.svg"),
    ("docs/assets/agent-collaboration-blueprint.svg", "agent-collaboration-blueprint.svg"),
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
    parser.add_argument("--template", default=DEFAULT_TEMPLATE_ID, help="Course template id for demo materials.")
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not remove the output directory before exporting.",
    )
    parser.add_argument(
        "--archive",
        type=Path,
        help="Optional zip archive path to create after exporting the package.",
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
    selected_template = export_demo_materials(output / "demo_materials", copied, missing, template_id=args.template)

    manifest = build_manifest(output, copied, missing, selected_template=selected_template)
    (output / "README.md").write_text(manifest, encoding="utf-8")
    (output / "submission_manifest.md").write_text(manifest, encoding="utf-8")
    (output / "START_HERE.md").write_text(build_start_here(selected_template), encoding="utf-8")
    (output / "index.html").write_text(build_submission_index(selected_template, missing), encoding="utf-8")
    write_checksums(output)

    print(f"[competition-package] exported to {output}")
    print(f"[competition-package] copied {len(copied)} file(s), missing {len(missing)} file(s).")
    if args.archive is not None:
        archive = create_archive(output, args.archive)
        print(f"[competition-package] archived to {archive}")
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


def create_archive(package_dir: Path, archive: Path) -> Path:
    archive = archive if archive.is_absolute() else ROOT / archive
    if archive.suffix.lower() != ".zip":
        archive = archive.with_suffix(".zip")
    resolved_archive = archive.resolve()
    resolved_package = package_dir.resolve()
    if resolved_archive == resolved_package or resolved_package in resolved_archive.parents:
        raise RuntimeError(f"Refuse to write archive inside package directory: {resolved_archive}")
    archive.parent.mkdir(parents=True, exist_ok=True)
    base_name = str(archive.with_suffix(""))
    created = shutil.make_archive(base_name, "zip", root_dir=package_dir.parent, base_dir=package_dir.name)
    return Path(created)


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


def export_demo_materials(target_dir: Path, copied: list[str], missing: list[str], *, template_id: str) -> dict[str, str]:
    template_path = ROOT / "data" / "course_templates" / f"{template_id}.json"
    if not template_path.exists():
        missing.append(f"data/course_templates/{template_id}.json")
        return {"id": template_id, "course_name": template_id}
    template = json.loads(template_path.read_text(encoding="utf-8"))
    selected = {
        "id": str(template.get("id") or template_id),
        "course_name": str(template.get("course_name") or template.get("title") or template_id),
    }
    target_dir.mkdir(parents=True, exist_ok=True)
    materials = {
        "README.md": build_demo_index(template, target_dir),
        "sparkweave-demo-deck-outline.md": build_deck_outline(template),
        "sparkweave-demo-deck.html": build_deck_html(template),
        "sparkweave-7min-recording-script.md": build_recording_script(template),
        "sparkweave-agent-collaboration-blueprint.md": build_agent_collaboration_blueprint(template),
        "sparkweave-demo-fallback-assets.md": build_demo_fallback_assets(template),
        "sparkweave-defense-qa.md": build_defense_qa(template),
        "sparkweave-competition-scorecard.md": build_competition_scorecard(template),
        "sparkweave-learning-effect-summary.md": build_learning_effect_demo_summary(template),
        "sparkweave-evaluator-one-pager.md": build_evaluator_one_pager(template),
        "sparkweave-final-pitch-checklist.md": build_final_pitch_checklist(template),
    }
    for name, content in materials.items():
        target = target_dir / name
        target.write_text(content, encoding="utf-8")
        copied.append(f"demo_materials/{name}")
    return selected


def copy_file(source: Path, target: Path, copied: list[str]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    copied.append(str(source.relative_to(ROOT)).replace("\\", "/"))


def write_checksums(package_dir: Path) -> Path:
    checksum_path = package_dir / "checksums.sha256"
    lines: list[str] = []
    for path in sorted(item for item in package_dir.rglob("*") if item.is_file()):
        if path == checksum_path:
            continue
        relative = path.relative_to(package_dir).as_posix()
        lines.append(f"{sha256_file(path)}  {relative}")
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return checksum_path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(output: Path, copied: list[str], missing: list[str], *, selected_template: dict[str, str]) -> str:
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
        f"- 演示课程：{selected_template.get('course_name', selected_template.get('id', '未指定'))}",
        "",
        "## 文件夹说明",
        "",
        "- `docs/`：项目说明、架构、能力、导学、学习画像、比赛路线图、演示 Runbook 和 AI Coding 说明。",
        "- `course_templates/`：可复现的完整高校课程样例，适合录屏和答辩现场演示。",
        "- `demo_materials/`：离线生成的 PPT 骨架、可打印演示页、评委一页说明、7 分钟录屏讲稿、多智能体协作蓝图、稳定兜底素材、评分点证据表、学习效果闭环摘要、答辩问答预案和最终答辩清单。",
        "- `screenshots/`：当前前端关键页面截图，可直接放入 PPT 或项目展示页。",
        "- `assets/`：Logo、系统架构图和导学闭环图。",
        "- `runtime/`：环境样例、依赖清单、启动脚本和安装检查脚本。",
        "- `checksums.sha256`：提交包文件完整性校验清单。",
        "",
        "## 赛题提交物映射",
        "",
        "| 提交物 | 本包对应材料 |",
        "| --- | --- |",
        "| 演示 PPT | `demo_materials/sparkweave-evaluator-one-pager.md`、`demo_materials/sparkweave-demo-deck-outline.md`、`demo_materials/sparkweave-demo-deck.html`、`demo_materials/sparkweave-agent-collaboration-blueprint.md`、`demo_materials/sparkweave-demo-fallback-assets.md`、`demo_materials/sparkweave-competition-scorecard.md`、`demo_materials/sparkweave-final-pitch-checklist.md`、`docs/competition-demo-runbook.md`、`screenshots/` |",
        "| 可运行源码与配置 | GitHub 仓库源码、`runtime/.env.example`、`runtime/requirements*.txt`、`runtime/scripts/start_web.py` |",
        "| 7 分钟演示视频 | `demo_materials/sparkweave-7min-recording-script.md`、`demo_materials/sparkweave-demo-fallback-assets.md`、`docs/competition-demo-runbook.md` 的分镜和兜底动作 |",
        "| 完整高校课程 | `course_templates/` 中的 ROS、高数、大模型教育智能体课程模板 |",
        "| 多智能体资源生成 | `demo_materials/sparkweave-agent-collaboration-blueprint.md`、`docs/capabilities.md`、`docs/guided-learning.md`、`docs/architecture.md` |",
        "| 学习效果评估 | `demo_materials/sparkweave-learning-effect-summary.md`、`docs/guided-learning.md`、`docs/learner-profile-design.md`、课程产出包 Markdown 导出 |",
        "| 答辩问答 | `demo_materials/sparkweave-defense-qa.md`、课程产出包中的答辩问答预案 |",
        "| 科大讯飞工具说明 | `docs/iflytek-integration.md`、`docs/configuration.md`、设置页快速检测 |",
        "| AI Coding 说明 | `docs/ai-coding-statement.md` |",
        "",
        "## 建议使用顺序",
        "",
        "1. 先按 `docs/getting-started.md` 和 `runtime/scripts/check_install.py` 确认环境。",
        "2. 先用 `demo_materials/` 离线材料搭 PPT、视频脚本和答辩问答骨架。",
        f"3. 运行 Web 后打开 `/guide`，优先选择“{selected_template.get('course_name', '大模型教育智能体系统开发')}”课程。",
        "4. 按 `docs/competition-demo-runbook.md` 录制 7 分钟演示视频。",
        "5. 使用导学页的课程产出包和学习报告 Markdown 下载按钮，把真实 session 证据补入 PPT 和提交文档。",
        "6. 赛前再次运行 `python scripts/check_course_templates.py`、`cd web && npm run build`。",
    ]
    if missing:
        lines.extend(["", "## 缺失文件", ""])
        lines.extend(f"- `{item}`" for item in missing)
    return "\n".join(lines) + "\n"


def build_start_here(selected_template: dict[str, str]) -> str:
    course_name = selected_template.get("course_name", selected_template.get("id", "大模型教育智能体系统开发"))
    return "\n".join(
        [
            "# 先看这里",
            "",
            "这是一份 SparkWeave 星火织学比赛提交包。解压后不需要从一堆文件里找入口，按下面顺序看即可。",
            "",
            "## 1. 先打开入口页",
            "",
            "- 打开 `index.html`。",
            "- 它会带你进入演示页、评分点证据、7 分钟讲稿、关键截图和运行说明。",
            "",
            "## 2. 快速理解项目",
            "",
            "- `demo_materials/sparkweave-evaluator-one-pager.md`：评委一页说明。",
            "- `demo_materials/sparkweave-competition-scorecard.md`：赛题五项要求证据表。",
            "- `demo_materials/sparkweave-learning-effect-summary.md`：学习效果评估闭环摘要。",
            "- `demo_materials/sparkweave-demo-deck.html`：可直接打开的演示页。",
            "",
            "## 3. 录屏或答辩",
            "",
            "- `demo_materials/sparkweave-7min-recording-script.md`：7 分钟演示视频讲稿。",
            "- `docs/competition-demo-runbook.md`：录屏路径和兜底动作。",
            f"- 推荐演示课程：{course_name}。",
            "",
            "## 4. 运行和复核",
            "",
            "- `docs/getting-started.md`：从安装到启动。",
            "- `runtime/scripts/start_web.py`：本地启动入口。",
            "- `checksums.sha256`：文件完整性校验清单。",
            "- 如需复核提交包，请运行：`python runtime/scripts/verify_competition_package.py .`。",
            "",
        ]
    )


def build_submission_index(selected_template: dict[str, str], missing: list[str]) -> str:
    course_name = escape(selected_template.get("course_name", selected_template.get("id", "大模型教育智能体系统开发")))
    missing_note = (
        "<p class=\"warning\">当前提交包存在缺失文件，请先查看 <a href=\"submission_manifest.md\">提交包索引</a>。</p>"
        if missing
        else "<p class=\"success\">提交包基础材料已齐全，可直接用于演示彩排和人工核对。</p>"
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SparkWeave 星火织学提交包</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7fafc;
      --surface: #ffffff;
      --text: #111827;
      --muted: #5f6b76;
      --line: #dde5e8;
      --primary: #0f766e;
      --blue: #2563eb;
      --red: #e60012;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", Arial, sans-serif;
      line-height: 1.62;
    }}
    main {{
      width: min(1120px, calc(100% - 32px));
      margin: 0 auto;
      padding: 36px 0 48px;
    }}
    header {{
      display: grid;
      grid-template-columns: 76px 1fr;
      gap: 18px;
      align-items: center;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--line);
    }}
    .logo {{
      width: 76px;
      height: 76px;
      object-fit: contain;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px;
    }}
    h1, h2, h3, p {{ margin: 0; }}
    h1 {{ font-size: 28px; line-height: 1.2; }}
    h2 {{ margin-top: 30px; font-size: 20px; }}
    h3 {{ font-size: 16px; }}
    .lead {{ margin-top: 10px; color: var(--muted); max-width: 760px; }}
    .badge {{
      display: inline-flex;
      align-items: center;
      margin-top: 14px;
      padding: 5px 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      color: var(--primary);
      font-size: 13px;
      font-weight: 700;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
      gap: 12px;
      margin-top: 14px;
    }}
    .card {{
      display: block;
      min-height: 124px;
      padding: 16px;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      text-decoration: none;
      color: inherit;
      transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
    }}
    .card:hover {{
      transform: translateY(-2px);
      border-color: rgba(15, 118, 110, 0.42);
      box-shadow: 0 10px 22px rgba(17, 24, 39, 0.08);
    }}
    .card p {{ margin-top: 8px; color: var(--muted); font-size: 14px; }}
    .tag {{ color: var(--blue); font-size: 13px; font-weight: 700; }}
    .proof {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 10px;
      margin-top: 14px;
    }}
    .proof span {{
      padding: 10px 12px;
      background: var(--surface);
      border: 1px solid var(--line);
      border-left: 3px solid var(--primary);
      border-radius: 8px;
      font-size: 14px;
    }}
    .screens {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      margin-top: 14px;
    }}
    figure {{
      margin: 0;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    figure img {{
      display: block;
      width: 100%;
      aspect-ratio: 16 / 10;
      object-fit: cover;
      border-bottom: 1px solid var(--line);
    }}
    figcaption {{ padding: 10px 12px; color: var(--muted); font-size: 14px; }}
    .success, .warning {{
      margin-top: 16px;
      padding: 12px 14px;
      border-radius: 8px;
      background: var(--surface);
      border: 1px solid var(--line);
    }}
    .success {{ border-left: 3px solid var(--primary); }}
    .warning {{ border-left: 3px solid var(--red); }}
    a {{ color: var(--blue); }}
    @media (max-width: 640px) {{
      main {{ width: min(100% - 20px, 1120px); padding-top: 22px; }}
      header {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: 24px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <img class="logo" src="assets/logo-ver2.png" alt="SparkWeave logo" />
      <div>
        <h1>SparkWeave 星火织学提交包</h1>
        <p class="lead">面向高校课程学习的多智能体个性化学习系统。当前演示课程：{course_name}。</p>
        <span class="badge">A3 基于大模型的个性化资源生成与学习多智能体系统开发</span>
      </div>
    </header>

    {missing_note}

    <h2>先看这几项</h2>
    <section class="grid" aria-label="核心材料">
      <a class="card" href="START_HERE.md"><span class="tag">入口</span><h3>先看这里</h3><p>解压后的最短阅读顺序和复核命令。</p></a>
      <a class="card" href="demo_materials/sparkweave-demo-deck.html"><span class="tag">演示页</span><h3>可打开的 PPT 骨架</h3><p>用于快速讲清项目价值、五项赛题对齐和演示路线。</p></a>
      <a class="card" href="demo_materials/sparkweave-evaluator-one-pager.md"><span class="tag">评委一页纸</span><h3>项目速览</h3><p>把定位、证据链、录屏路线和兜底材料压缩到一页。</p></a>
      <a class="card" href="demo_materials/sparkweave-competition-scorecard.md"><span class="tag">评分点</span><h3>赛题证据表</h3><p>逐条映射画像、资源生成、路径规划、智能辅导和学习评估。</p></a>
      <a class="card" href="demo_materials/sparkweave-learning-effect-summary.md"><span class="tag">评估闭环</span><h3>学习效果摘要</h3><p>单独说明证据、画像、处方和动态调整如何形成闭环。</p></a>
      <a class="card" href="demo_materials/sparkweave-7min-recording-script.md"><span class="tag">录屏</span><h3>7 分钟讲稿</h3><p>按时间段给出画面、讲述词和现场兜底动作。</p></a>
    </section>

    <h2>五项要求证据</h2>
    <section class="proof" aria-label="赛题五项要求">
      <span>对话式学习画像自主构建</span>
      <span>多智能体协同资源生成</span>
      <span>个性化路径规划与资源推送</span>
      <span>多模态智能辅导</span>
      <span>学习效果评估闭环</span>
    </section>

    <h2>关键截图</h2>
    <section class="screens" aria-label="页面截图">
      <figure><img src="screenshots/screenshots-refined-chat.png" alt="学习工作台截图" /><figcaption>学习工作台</figcaption></figure>
      <figure><img src="screenshots/screenshots-simplified-guide.png" alt="导学页面截图" /><figcaption>懒人式导学</figcaption></figure>
      <figure><img src="screenshots/screenshots-simplified-final-knowledge.png" alt="知识库页面截图" /><figcaption>资料与知识库</figcaption></figure>
      <figure><img src="screenshots/screenshots-simplified-final-settings.png" alt="设置页面截图" /><figcaption>服务配置检测</figcaption></figure>
    </section>

    <h2>更多材料</h2>
    <section class="grid" aria-label="更多材料">
      <a class="card" href="submission_manifest.md"><span class="tag">索引</span><h3>提交包清单</h3><p>查看目录说明、材料映射、建议使用顺序和缺失项。</p></a>
      <a class="card" href="docs/architecture.md"><span class="tag">架构</span><h3>系统架构说明</h3><p>后端、前端、多智能体和运行时能力的整体说明。</p></a>
      <a class="card" href="assets/architecture.svg"><span class="tag">图示</span><h3>系统架构图</h3><p>可直接放入 PPT 或答辩材料。</p></a>
      <a class="card" href="docs/getting-started.md"><span class="tag">运行</span><h3>启动与配置</h3><p>从依赖安装、环境变量到本地启动的最短路径。</p></a>
      <a class="card" href="checksums.sha256"><span class="tag">校验</span><h3>文件完整性</h3><p>用于核对提交包文件是否在传输或二次打包中被改动。</p></a>
    </section>
  </main>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
