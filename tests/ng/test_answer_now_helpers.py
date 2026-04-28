from __future__ import annotations

from sparkweave.graphs._answer_now import (
    answer_now_body,
    answer_now_metadata,
    answer_now_progress_metadata,
    answer_now_user_prompt,
)


def test_answer_now_user_prompt_builds_shared_context_block():
    prompt = answer_now_user_prompt(
        original="Explain Fourier transform",
        partial="Partial draft",
        trace_summary="1. thinking: frequency intuition",
        extra_context="Mode: quick",
        final_instruction="Answer now.",
    )

    assert "Original user request:\nExplain Fourier transform" in prompt
    assert "Mode: quick" in prompt
    assert "[Current Draft]\nPartial draft" in prompt
    assert "[Execution Trace]\n1. thinking: frequency intuition" in prompt
    assert prompt.endswith("Answer now.")


def test_answer_now_user_prompt_supports_custom_labels_and_empty_partial():
    prompt = answer_now_user_prompt(
        original="Research topic",
        original_label="Topic",
        partial="",
        trace_summary="Trace",
        trace_label="Research Trace",
    )

    assert prompt.startswith("Topic:\nResearch topic")
    assert "[Current Draft]\n(empty)" in prompt
    assert "[Research Trace]\nTrace" in prompt


def test_answer_now_metadata_helpers_keep_flag_consistent():
    assert answer_now_progress_metadata("running") == {
        "trace_kind": "call_status",
        "call_state": "running",
        "answer_now": True,
    }
    assert answer_now_metadata(runtime="langgraph") == {
        "answer_now": True,
        "runtime": "langgraph",
    }


def test_answer_now_body_prefixes_notice_when_present():
    assert answer_now_body("Final", notice="> Skipped planning") == "> Skipped planning\n\nFinal"
    assert answer_now_body("Final") == "Final"


