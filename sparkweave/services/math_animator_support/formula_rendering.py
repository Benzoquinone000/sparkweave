"""Helpers that make generated Manim formulas easier to read in videos."""

from __future__ import annotations

import re

FORMULA_HELPER_MARKER = "SparkWeave formula rendering helpers"

_FORMULA_CALL_RE = re.compile(r"\b(?:MathTex|Tex)\s*\(")
_MANIM_IMPORT_RE = re.compile(
    r"^(\s*(?:from\s+manim\s+import\s+[^\n]+|import\s+manim(?:\s+as\s+\w+)?)\s*)$",
    re.MULTILINE,
)


def prepare_manim_formula_code(code: str) -> str:
    """Repair common formula syntax issues, then inject rendering defaults."""
    repaired = repair_bare_latex_arguments(code)
    repaired = repair_unicode_axis_labels(repaired)
    repaired = repair_axes_length_attributes(repaired)
    return enhance_formula_rendering(repaired)


def repair_axes_length_attributes(code: str) -> str:
    """Map older/generated Axes length aliases to Manim's actual properties."""
    return (code or "").replace(".x_axis_length", ".x_axis.length").replace(
        ".y_axis_length", ".y_axis.length"
    )


def repair_unicode_axis_labels(code: str) -> str:
    """Convert non-ASCII axis label strings to Text objects.

    Manim's ``Axes.get_axis_labels(x_label="中文")`` routes the string through
    TeX, which fails for ordinary Chinese labels in a default LaTeX setup.
    Passing ``Text("中文")`` keeps labels renderable.
    """

    def _replace(match: re.Match[str]) -> str:
        key = match.group("key")
        quote = match.group("quote")
        content = match.group("content")
        if content.isascii():
            return match.group(0)
        escaped = content.replace("\\", "\\\\").replace('"', r"\"")
        return f'{key}=Text("{escaped}", font_size=24)'

    return re.sub(
        r"(?P<key>[xy]_label)\s*=\s*(?P<quote>[\"'])(?P<content>.*?)(?P=quote)",
        _replace,
        code or "",
    )


def repair_bare_latex_arguments(code: str) -> str:
    """Quote bare LaTeX lines accidentally emitted inside MathTex/Tex calls.

    A common LLM failure is:

        MathTex(
            r_t(\\theta) = \\frac{...},
            font_size=42,
        )

    Python cannot parse that. We convert the first argument to a raw string and
    leave normal, already quoted calls untouched.
    """
    lines = (code or "").splitlines()
    repaired = list(lines)
    call_start_re = re.compile(r"\b(?:MathTex|Tex)\s*\(\s*$")
    string_prefix_re = re.compile(r"(?i)^(?:r|u|f|fr|rf|br|rb)?[\"']")
    keyword_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*=")

    for index, line in enumerate(lines[:-1]):
        if not call_start_re.search(line.strip()):
            continue
        next_index = index + 1
        while next_index < len(lines) and not lines[next_index].strip():
            next_index += 1
        if next_index >= len(lines):
            continue

        candidate = lines[next_index]
        stripped = candidate.strip()
        if not stripped or string_prefix_re.match(stripped) or keyword_re.match(stripped):
            continue
        if stripped.startswith(("*", "#", ")")):
            continue
        if not _looks_like_latex_formula(stripped):
            continue

        trailing_comma = stripped.endswith(",")
        formula = stripped[:-1].strip() if trailing_comma else stripped
        formula = _normalize_bare_latex(formula)
        indent = candidate[: len(candidate) - len(candidate.lstrip())]
        repaired[next_index] = f'{indent}r"{formula}",'

    return "\n".join(repaired) + ("\n" if (code or "").endswith("\n") else "")


def enhance_formula_rendering(code: str) -> str:
    """Inject a tiny MathTex/Tex wrapper into generated Manim code.

    LLM-generated animations often render equations too large for the frame or
    forget to change formula color on white backgrounds. The wrapper keeps the
    original call sites working while applying conservative defaults.
    """
    source = code or ""
    if FORMULA_HELPER_MARKER in source or not _FORMULA_CALL_RE.search(source):
        return source

    helper = _formula_helper(default_color=_default_formula_color(source))
    match = _MANIM_IMPORT_RE.search(source)
    if match:
        insert_at = match.end()
        head = source[:insert_at].rstrip()
        tail = source[insert_at:].lstrip("\n")
        return f"{head}\n\n{helper}\n{tail}"
    return f"from manim import *\n\n{helper}\n{source}"


def _default_formula_color(code: str) -> str:
    if _uses_light_background(code):
        return "BLACK"
    return "None"


def _uses_light_background(code: str) -> bool:
    compact = re.sub(r"\s+", "", code).lower()
    light_tokens = (
        "background_color=white",
        "background_color=\"#fff",
        "background_color='#fff",
        "background_color=\"#fcfcfc",
        "background_color='#fcfcfc",
        "background_color=\"#f7fafc",
        "background_color='#f7fafc",
    )
    return any(token in compact for token in light_tokens)


def _looks_like_latex_formula(text: str) -> bool:
    return any(marker in text for marker in ("\\", "^", "_", "=", "{", "}"))


def _normalize_bare_latex(text: str) -> str:
    formula = text.strip()
    formula = formula.replace("\\\\", "\\")
    return formula.replace('"', r"\"")


def _formula_helper(*, default_color: str) -> str:
    return f"""# {FORMULA_HELPER_MARKER}
_SW_ORIGINAL_MATHTEX = MathTex
_SW_ORIGINAL_TEX = Tex
_SW_FORMULA_DEFAULT_COLOR = {default_color}


def _sw_fit_formula(mobject, max_width=None, max_height=None):
    frame_width = float(getattr(config, "frame_width", 14.222))
    frame_height = float(getattr(config, "frame_height", 8.0))
    max_width = float(max_width or frame_width - 1.0)
    max_height = float(max_height or frame_height * 0.32)
    if getattr(mobject, "width", 0) > max_width:
        mobject.scale_to_fit_width(max_width)
    if getattr(mobject, "height", 0) > max_height:
        mobject.scale_to_fit_height(max_height)
    return mobject


def MathTex(*tex_strings, **kwargs):
    kwargs.setdefault("font_size", 40)
    if _SW_FORMULA_DEFAULT_COLOR is not None and "color" not in kwargs:
        kwargs["color"] = _SW_FORMULA_DEFAULT_COLOR
    return _sw_fit_formula(_SW_ORIGINAL_MATHTEX(*tex_strings, **kwargs))


def Tex(*tex_strings, **kwargs):
    kwargs.setdefault("font_size", 36)
    if _SW_FORMULA_DEFAULT_COLOR is not None and "color" not in kwargs:
        kwargs["color"] = _SW_FORMULA_DEFAULT_COLOR
    return _sw_fit_formula(_SW_ORIGINAL_TEX(*tex_strings, **kwargs))
"""


__all__ = [
    "FORMULA_HELPER_MARKER",
    "enhance_formula_rendering",
    "prepare_manim_formula_code",
    "repair_axes_length_attributes",
    "repair_bare_latex_arguments",
    "repair_unicode_axis_labels",
]
