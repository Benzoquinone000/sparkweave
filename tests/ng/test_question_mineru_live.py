from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

from sparkweave.services.question import (
    check_mineru_installed,
    load_parsed_paper,
    parse_pdf_with_mineru,
)


def _mineru_live_enabled() -> bool:
    return os.getenv("SPARKWEAVE_NG_MINERU_LIVE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _skip_reason() -> str:
    if not _mineru_live_enabled():
        return "Set SPARKWEAVE_NG_MINERU_LIVE=1 to run live MinerU PDF parsing smoke tests."
    if check_mineru_installed() is None:
        return "MinerU CLI is not available in this Python environment."
    missing = [
        package
        for package in ("PIL", "reportlab")
        if importlib.util.find_spec(package) is None
    ]
    if missing:
        return f"Missing package(s) needed to generate smoke PDFs: {', '.join(missing)}."
    return ""


def _write_text_pdf(path: Path) -> None:
    from reportlab.pdfgen import canvas

    pdf = canvas.Canvas(str(path), pagesize=(612, 792))
    pdf.setFont("Helvetica", 14)
    pdf.drawString(72, 700, "Question 1: What is 2 + 2?")
    pdf.drawString(72, 670, "A. 3    B. 4    C. 5    D. 6")
    pdf.drawString(72, 640, "Answer: B")
    pdf.save()


def _write_multipage_image_pdf(path: Path) -> None:
    from PIL import Image, ImageDraw

    font = _load_smoke_font()

    pages = []
    for index, prompt in enumerate(
        [
            "Question 1: What is 3 + 5?",
            "Question 2: What is 10 - 4?",
        ],
        start=1,
    ):
        image = Image.new("RGB", (1200, 700), "white")
        draw = ImageDraw.Draw(image)
        draw.text((80, 120), prompt, fill="black", font=font)
        draw.text((80, 240), "A. 6    B. 7    C. 8    D. 9", fill="black", font=font)
        draw.text((80, 360), f"Page {index}", fill="black", font=font)
        pages.append(image)

    pages[0].save(path, "PDF", resolution=150.0, save_all=True, append_images=pages[1:])


def _load_smoke_font():
    from PIL import ImageFont

    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), 48)
    return ImageFont.load_default()


def _parse_and_load(pdf_path: Path, output_dir: Path) -> str:
    assert parse_pdf_with_mineru(str(pdf_path), str(output_dir)) is True
    markdown, content_list, _images_dir = load_parsed_paper(output_dir / pdf_path.stem)
    assert markdown
    assert isinstance(content_list, list)
    return markdown


@pytest.mark.live
def test_live_mineru_parses_text_and_multipage_ocr_pdf(tmp_path, monkeypatch) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    monkeypatch.setenv("SPARKWEAVE_MINERU_TIMEOUT", "240")

    text_pdf = tmp_path / "text_exam.pdf"
    _write_text_pdf(text_pdf)
    monkeypatch.setenv("SPARKWEAVE_MINERU_ARGS", "-m txt -b pipeline")
    text_markdown = _parse_and_load(text_pdf, tmp_path / "text_out")
    assert "Question" in text_markdown

    ocr_pdf = tmp_path / "ocr_exam.pdf"
    _write_multipage_image_pdf(ocr_pdf)
    monkeypatch.setenv("SPARKWEAVE_MINERU_ARGS", "-m ocr -b pipeline -l en -f false -t false")
    ocr_markdown = _parse_and_load(ocr_pdf, tmp_path / "ocr_out")
    assert len(ocr_markdown.strip()) >= 3


