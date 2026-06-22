from __future__ import annotations

from sparkweave.services.learning_effect import ConceptMasteryState, NextBestAction
from sparkweave.services.learning_effect_support import LEARNING_EFFECT_DIMENSION_WEIGHTS


def test_learning_effect_models_keep_defaults() -> None:
    concept = ConceptMasteryState(concept_id="limits", title="Limits")
    action = NextBestAction(id="a1", type="diagnostic", title="Start", reason="Need baseline")

    assert concept.status == "unknown"
    assert action.writes_back == ["mastery", "profile"]
    assert "mastery" in LEARNING_EFFECT_DIMENSION_WEIGHTS
