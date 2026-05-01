from __future__ import annotations

from sparkweave.services.math_animator_support.formula_rendering import (
    FORMULA_HELPER_MARKER,
    enhance_formula_rendering,
    repair_axes_length_attributes,
    repair_bare_latex_arguments,
    repair_unicode_axis_labels,
)


def test_enhance_formula_rendering_injects_after_manim_import() -> None:
    code = "from manim import *\n\nclass MainScene(Scene):\n    def construct(self):\n        formula = MathTex('a^2+b^2=c^2')\n"

    enhanced = enhance_formula_rendering(code)

    assert enhanced.startswith("from manim import *\n\n# SparkWeave formula rendering helpers")
    assert FORMULA_HELPER_MARKER in enhanced
    assert "_SW_ORIGINAL_MATHTEX = MathTex" in enhanced
    assert "def MathTex(*tex_strings, **kwargs):" in enhanced
    assert "formula = MathTex('a^2+b^2=c^2')" in enhanced


def test_enhance_formula_rendering_uses_black_default_on_white_background() -> None:
    code = (
        "from manim import *\n\n"
        "class MainScene(Scene):\n"
        "    def construct(self):\n"
        "        self.camera.background_color = WHITE\n"
        "        formula = MathTex('x^2')\n"
    )

    enhanced = enhance_formula_rendering(code)

    assert "_SW_FORMULA_DEFAULT_COLOR = BLACK" in enhanced


def test_enhance_formula_rendering_is_idempotent() -> None:
    code = "from manim import *\n\nclass MainScene(Scene):\n    def construct(self):\n        formula = MathTex('x')\n"

    enhanced = enhance_formula_rendering(code)

    assert enhance_formula_rendering(enhanced) == enhanced


def test_enhance_formula_rendering_leaves_non_formula_code_unchanged() -> None:
    code = "from manim import *\n\nclass MainScene(Scene):\n    def construct(self):\n        self.add(Text('hello'))\n"

    assert enhance_formula_rendering(code) == code


def test_repair_bare_latex_arguments_quotes_common_llm_syntax_error() -> None:
    code = (
        "from manim import *\n\n"
        "class MainScene(Scene):\n"
        "    def construct(self):\n"
        "        formula = MathTex(\n"
        "            r_t(\\\\theta) = \\\\frac{\\\\pi_\\\\theta(a_t|s_t)}{\\\\pi_{old}(a_t|s_t)},\n"
        "            font_size=42\n"
        "        )\n"
    )

    repaired = repair_bare_latex_arguments(code)

    assert 'r"r_t(\\theta) = \\frac{\\pi_\\theta(a_t|s_t)}{\\pi_{old}(a_t|s_t)}",' in repaired
    compile(repaired, "<scene>", "exec")


def test_repair_bare_latex_arguments_keeps_quoted_formula_unchanged() -> None:
    code = "formula = MathTex(\n    r\"x^2\",\n    font_size=42\n)\n"

    assert repair_bare_latex_arguments(code) == code


def test_repair_unicode_axis_labels_wraps_chinese_labels_in_text() -> None:
    code = 'labels = axes.get_axis_labels(x_label="更新步数", y_label="回报")\n'

    repaired = repair_unicode_axis_labels(code)

    assert 'x_label=Text("更新步数", font_size=24)' in repaired
    assert 'y_label=Text("回报", font_size=24)' in repaired
    compile("from manim import *\n" + repaired, "<scene>", "exec")


def test_repair_unicode_axis_labels_keeps_ascii_labels_as_tex_strings() -> None:
    code = 'labels = axes.get_axis_labels(x_label="r_t", y_label="clip(r_t)")\n'

    assert repair_unicode_axis_labels(code) == code


def test_repair_axes_length_attributes_uses_manim_axis_properties() -> None:
    code = "width = axes.x_axis_length\nheight = axes.y_axis_length\n"

    repaired = repair_axes_length_attributes(code)

    assert repaired == "width = axes.x_axis.length\nheight = axes.y_axis.length\n"
