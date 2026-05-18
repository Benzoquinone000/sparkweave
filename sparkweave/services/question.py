"""Question parsing helpers for NG deep-question workflows."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from typing import Any

from sparkweave.core.json import parse_json_response
from sparkweave.services.llm import complete as llm_complete
from sparkweave.services.llm import get_llm_config, get_token_limit_kwargs

logger = logging.getLogger(__name__)


class QuestionParsingUnavailable(ImportError):
    """Raised when optional question parsing dependencies are unavailable."""


def check_mineru_installed() -> str | None:
    """Return the available MinerU command name, if installed."""
    for command in _candidate_mineru_commands():
        if _mineru_command_available(command):
            return command
    return None


def _candidate_mineru_commands() -> list[str]:
    candidates: list[str] = []
    configured = os.getenv("SPARKWEAVE_MINERU_COMMAND", "").strip()
    if configured:
        candidates.append(configured)

    command_names = ("magic-pdf", "mineru")
    candidates.extend(command_names)

    python_dir = Path(sys.executable).resolve().parent
    for command in command_names:
        candidates.extend(
            str(path)
            for path in (
                python_dir / "Scripts" / f"{command}.exe",
                python_dir / "Scripts" / command,
                python_dir / "bin" / command,
                python_dir / f"{command}.exe",
            )
        )

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = candidate.lower()
        if normalized not in seen:
            seen.add(normalized)
            deduped.append(candidate)
    return deduped


def _mineru_command_available(command: str) -> bool:
    for flag in ("--version", "--help"):
        try:
            result = subprocess.run(
                [command, flag],
                check=False,
                capture_output=True,
                text=True,
                shell=False,
                timeout=15,
            )
        except FileNotFoundError:
            return False
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            return True
    return False


def parse_pdf_with_mineru(pdf_path: str, output_base_dir: str | None = None) -> bool:
    """Parse a PDF with MinerU and place artifacts under *output_base_dir*."""
    mineru_cmd = check_mineru_installed()
    if not mineru_cmd:
        logger.warning("MinerU command is not available")
        return False

    source_pdf = Path(pdf_path).expanduser().resolve()
    if not source_pdf.exists() or source_pdf.suffix.lower() != ".pdf":
        logger.warning("Invalid PDF path for MinerU parsing: %s", source_pdf)
        return False

    if output_base_dir is None:
        output_root = Path.cwd() / "reference_papers"
    else:
        output_root = Path(output_base_dir).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    output_dir = output_root / source_pdf.stem
    if output_dir.exists():
        shutil.rmtree(output_dir)

    temp_output = output_root / "temp_mineru_output"
    if temp_output.exists():
        shutil.rmtree(temp_output)
    temp_output.mkdir(parents=True, exist_ok=True)

    try:
        extra_args = shlex.split(
            os.getenv("SPARKWEAVE_MINERU_ARGS", ""),
            posix=os.name != "nt",
        )
        result = subprocess.run(
            [mineru_cmd, "-p", str(source_pdf), "-o", str(temp_output), *extra_args],
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=_mineru_parse_timeout(),
        )
        if result.returncode != 0:
            logger.warning("MinerU failed for %s: %s", source_pdf, result.stderr)
            return False

        source_folder = _select_mineru_output_source(temp_output, source_pdf.stem)
        if source_folder is None:
            logger.warning("MinerU produced no files for %s", source_pdf)
            return False

        output_dir.mkdir(parents=True, exist_ok=True)
        if source_folder.is_dir():
            for item in source_folder.iterdir():
                destination = output_dir / item.name
                if destination.exists():
                    if destination.is_dir():
                        shutil.rmtree(destination)
                    else:
                        destination.unlink()
                shutil.move(str(item), str(destination))
        else:
            if output_dir.exists():
                shutil.rmtree(output_dir)
            shutil.move(str(source_folder), str(output_dir))
        return True
    except subprocess.TimeoutExpired:
        logger.warning("MinerU timed out while parsing %s", source_pdf)
        return False
    except Exception:
        logger.exception("Unexpected MinerU parsing failure for %s", source_pdf)
        return False
    finally:
        if temp_output.exists():
            shutil.rmtree(temp_output)


def _select_mineru_output_source(temp_output: Path, pdf_stem: str) -> Path | None:
    preferred = temp_output / pdf_stem
    if preferred.exists():
        return preferred

    generated = sorted(
        temp_output.iterdir(),
        key=lambda item: (not item.is_dir(), item.name.lower()),
    )
    if not generated:
        return None

    for item in generated:
        if item.is_dir():
            return item
    return temp_output


def _mineru_parse_timeout() -> float | None:
    raw = os.getenv("SPARKWEAVE_MINERU_TIMEOUT", "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        logger.warning("Ignoring invalid SPARKWEAVE_MINERU_TIMEOUT=%r", raw)
        return None
    return value if value > 0 else None


def _find_parsed_content_dir(paper_dir: Path) -> Path:
    """Locate the MinerU output directory that contains markdown artifacts."""
    candidate_dirs: list[Path] = []

    for preferred_name in ("auto", "hybrid_auto"):
        preferred_dir = paper_dir / preferred_name
        if preferred_dir.is_dir():
            candidate_dirs.append(preferred_dir)

    for child in sorted(paper_dir.iterdir()):
        if child.is_dir() and child not in candidate_dirs:
            candidate_dirs.append(child)

    nested_artifact_dirs = {
        artifact.parent
        for pattern in ("*.md", "*_content_list.json")
        for artifact in paper_dir.rglob(pattern)
    }
    for artifact_dir in sorted(nested_artifact_dirs):
        if artifact_dir not in candidate_dirs:
            candidate_dirs.append(artifact_dir)

    for candidate_dir in candidate_dirs:
        if list(candidate_dir.glob("*.md")):
            return candidate_dir
    return candidate_dirs[0] if candidate_dirs else paper_dir


def load_parsed_paper(paper_dir: Path) -> tuple[str | None, list[dict] | None, Path]:
    """Load markdown, optional content list, and images dir from MinerU output."""
    parsed_dir = _find_parsed_content_dir(paper_dir)
    md_files = list(parsed_dir.glob("*.md"))
    if not md_files:
        logger.warning("No markdown file found in %s", parsed_dir)
        return None, None, parsed_dir / "images"

    markdown_content = md_files[0].read_text(encoding="utf-8")
    content_list = None
    json_files = list(parsed_dir.glob("*_content_list.json"))
    if json_files:
        content_list = json.loads(json_files[0].read_text(encoding="utf-8"))
    return markdown_content, content_list, parsed_dir / "images"


def _supports_json_response_format(binding: str | None, model: str | None) -> bool:
    normalized_binding = str(binding or "").lower()
    normalized_model = str(model or "").lower()
    if normalized_binding in {"anthropic", "claude"}:
        return False
    return bool(normalized_model) and not normalized_model.startswith(("o1", "o3"))


def _run_complete_sync(**kwargs: Any) -> str:
    async def _call() -> str:
        return await llm_complete(**kwargs)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_call())

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(_call())).result()


def extract_questions_with_llm(
    markdown_content: str,
    content_list: list[dict] | None,
    images_dir: Path,
    api_key: str,
    base_url: str,
    model: str,
    api_version: str | None = None,
    binding: str | None = None,
) -> list[dict[str, Any]]:
    """Use the configured LLM to extract question metadata from parsed markdown."""
    image_list = [
        image.name
        for image in sorted(images_dir.glob("*"))
        if image.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    ] if images_dir.exists() else []

    system_prompt = (
        "You extract exam questions from parsed paper content. Return JSON with "
        'a top-level "questions" list. Each item must include question_number, '
        "question_text, and images. Preserve the original question wording and "
        "include multiple-choice options in question_text."
    )
    user_prompt = "\n\n".join(
        [
            "## Exam paper markdown",
            markdown_content[:15000],
            "## MinerU content list",
            json.dumps(content_list or [], ensure_ascii=False)[:6000],
            "## Available image files",
            json.dumps(image_list, ensure_ascii=False, indent=2),
        ]
    )

    llm_kwargs: dict[str, Any] = {
        "temperature": 0.2,
        **get_token_limit_kwargs(model, 4096),
    }
    if _supports_json_response_format(binding, model):
        llm_kwargs["response_format"] = {"type": "json_object"}

    result_text = _run_complete_sync(
        prompt=user_prompt,
        system_prompt=system_prompt,
        model=model,
        api_key=api_key,
        base_url=base_url,
        api_version=api_version,
        binding=binding,
        **llm_kwargs,
    )

    parsed = parse_json_response(result_text or "", logger_instance=logger, fallback={})
    questions = parsed.get("questions", []) if isinstance(parsed, dict) else []
    return questions if isinstance(questions, list) else []


def save_questions_json(
    questions: list[dict[str, Any]],
    output_dir: Path,
    paper_name: str,
) -> Path:
    """Save extracted question metadata as a timestamped JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"{paper_name}_{timestamp}_questions.json"
    payload = {
        "paper_name": paper_name,
        "extraction_time": datetime.now().isoformat(),
        "total_questions": len(questions),
        "questions": questions,
    }
    output_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_file


def extract_questions_from_paper(paper_dir: str, output_dir: str | None = None) -> bool:
    """Extract question JSON from a MinerU-parsed exam paper directory."""
    source_dir = Path(paper_dir).expanduser().resolve()
    if not source_dir.exists():
        logger.warning("Parsed paper directory does not exist: %s", source_dir)
        return False

    markdown_content, content_list, images_dir = load_parsed_paper(source_dir)
    if not markdown_content:
        return False

    try:
        llm_config = get_llm_config()
    except Exception:
        logger.exception("Unable to load LLM config for question extraction")
        return False

    questions = extract_questions_with_llm(
        markdown_content=markdown_content,
        content_list=content_list,
        images_dir=images_dir,
        api_key=llm_config.api_key,
        base_url=llm_config.base_url,
        model=llm_config.model,
        api_version=getattr(llm_config, "api_version", None),
        binding=getattr(llm_config, "binding", None),
    )
    if not questions:
        return False

    target_dir = source_dir if output_dir is None else Path(output_dir).expanduser().resolve()
    save_questions_json(questions, target_dir, source_dir.name)
    return True


__all__ = [
    "QuestionParsingUnavailable",
    "check_mineru_installed",
    "extract_questions_from_paper",
    "extract_questions_with_llm",
    "load_parsed_paper",
    "parse_pdf_with_mineru",
    "save_questions_json",
]


