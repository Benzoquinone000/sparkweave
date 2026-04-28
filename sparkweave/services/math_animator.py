"""Math animator service facade for optional render/review helpers."""

from __future__ import annotations

from typing import Any


def load_rendering_components() -> tuple[type[Exception], type[Any], type[Any]]:
    from sparkweave.services.math_animator_support.renderer import (
        ManimRenderError,
        ManimRenderService,
    )
    from sparkweave.services.math_animator_support.retry_manager import CodeRetryManager

    return ManimRenderError, ManimRenderService, CodeRetryManager


def load_generated_code_model() -> type[Any]:
    from sparkweave.services.math_animator_support.models import GeneratedCode

    return GeneratedCode


def load_visual_review_components() -> tuple[type[Any], type[Any], type[Any]]:
    from sparkweave.services.math_animator_support.models import (
        RenderResult,
        VisualReviewResult,
    )
    from sparkweave.services.math_animator_support.visual_review import (
        VisualReviewService,
    )

    return RenderResult, VisualReviewResult, VisualReviewService


__all__ = [
    "load_generated_code_model",
    "load_rendering_components",
    "load_visual_review_components",
]

