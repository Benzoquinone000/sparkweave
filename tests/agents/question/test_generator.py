from __future__ import annotations

import pytest

from sparkweave.agents.question import Generator, QuestionTemplate


class StubGenerator(Generator):
    def __init__(self, repaired_payload: dict | None = None) -> None:
        self._repaired_payload = repaired_payload or {}

    async def _repair_payload(self, **kwargs):  # type: ignore[override]
        return self._repaired_payload


@pytest.mark.asyncio
async def test_generator_repairs_coding_question_that_looks_like_multiple_choice() -> None:
    generator = StubGenerator(
        repaired_payload={
            "question_type": "coding",
            "question": "Write pseudocode that alternates answer order across iterations to mitigate positional bias.",
            "options": None,
            "correct_answer": "for i in range(total_iterations):\n    if i % 2 == 0:\n        prompt = f\"{query} Answer 1: {answer1} Answer 2: {answer2}\"\n    else:\n        prompt = f\"{query} Answer 1: {answer2} Answer 2: {answer1}\"\n    evaluate(prompt)",
            "explanation": "Alternate the two answers deterministically so each appears in each position equally often.",
        }
    )
    template = QuestionTemplate(
        question_id="q_3",
        concentration="win-rate comparison positional bias mitigation",
        question_type="coding",
        difficulty="hard",
    )
    invalid_payload = {
        "question_type": "coding",
        "question": "Select the code logic that best mitigates positional bias across iterations.",
        "options": {
            "A": "fixed order",
            "B": "alternate order every iteration",
            "C": "randomize order",
            "D": "always reverse order",
        },
        "correct_answer": "B",
        "explanation": "B is correct.",
    }

    normalized, validation = await generator._validate_and_repair_payload(
        template=template,
        payload=invalid_payload,
        user_topic="win-rate comparison",
        preference="",
        history_context="",
        knowledge_context="",
        available_tools="(no tools available)",
    )

    assert normalized["question_type"] == "coding"
    assert normalized["options"] is None
    assert normalized["correct_answer"].startswith("for i in range")
    assert validation["repaired"] is True
    assert validation["schema_ok"] is True
    assert validation["issues"] == []


def test_generator_normalizes_choice_answer_from_option_text() -> None:
    payload = Generator._normalize_payload_shape(
        "choice",
        {
            "question_type": "choice",
            "question": "Which option is correct?",
            "options": {
                "a": "Alpha",
                "b": "Beta",
                "c": "Gamma",
                "d": "Delta",
            },
            "correct_answer": "Gamma",
            "explanation": "Because gamma matches the requirement.",
        },
    )

    assert payload["options"] == {
        "A": "Alpha",
        "B": "Beta",
        "C": "Gamma",
        "D": "Delta",
    }
    assert payload["correct_answer"] == "C"


def test_generator_normalizes_true_false_and_fill_blank_questions() -> None:
    judgement = Generator._normalize_payload_shape(
        "true_false",
        {
            "question_type": "判断题",
            "question": "梯度下降一定能找到全局最优解。",
            "correct_answer": "错误",
            "explanation": "非凸目标中可能收敛到局部最优或鞍点。",
        },
    )
    blank = Generator._normalize_payload_shape(
        "fill_blank",
        {
            "question_type": "fill_blank",
            "question": "反向传播使用链式法则计算参数的",
            "correct_answer": "梯度",
            "explanation": "链式法则将损失对参数的导数逐层传回。",
        },
    )

    assert judgement["question_type"] == "true_false"
    assert judgement["correct_answer"] == "False"
    assert judgement["options"] == {"True": "正确", "False": "错误"}
    assert blank["question_type"] == "fill_blank"
    assert "____" in blank["question"]
    assert Generator._collect_payload_issues("fill_blank", blank) == []

