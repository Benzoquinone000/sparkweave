from __future__ import annotations

import pytest

from sparkweave.services.rag_support.retrieval_policy import (
    build_retrieval_policy,
    infer_retrieval_profile,
    normalize_retrieval_profile,
)


def test_normalize_retrieval_profile_aliases() -> None:
    assert normalize_retrieval_profile("balanced") == "concept"
    assert normalize_retrieval_profile("exact-match") == "exact"
    assert normalize_retrieval_profile("learning-path") == "guide"
    assert normalize_retrieval_profile("unknown") == "auto"


def test_infer_profile_for_code_formula_and_guide_queries() -> None:
    assert infer_retrieval_profile("DataLoader 报错应该看哪个代码文件？")[0] == "code"
    assert infer_retrieval_profile("交叉熵损失函数公式怎么推导？")[0] == "formula"
    assert infer_retrieval_profile("我 PCA 学不会，先补什么路线？")[0] == "guide"


@pytest.mark.parametrize(
    ("query", "expected_profile"),
    [
        ("PCA", "fast"),
        ("What is gradient descent?", "concept"),
        ("Which chapter defines gradient descent?", "exact"),
        ("Explain train_step(batch) implementation", "code"),
        ("How do we derive x^2 = 4?", "formula"),
        ("Build a learning path for PCA", "guide"),
        ("Compare and summarize PCA and SVD", "broad"),
    ],
)
def test_auto_inference_can_select_every_retrieval_profile(query: str, expected_profile: str) -> None:
    assert infer_retrieval_profile(query)[0] == expected_profile


@pytest.mark.parametrize(
    "profile",
    ["fast", "concept", "exact", "code", "formula", "guide", "broad"],
)
def test_build_policy_can_force_every_profile(profile: str) -> None:
    policy = build_retrieval_policy("Explain gradient descent", profile=profile)

    assert policy.profile == profile
    assert policy.reason == "forced_profile"
    assert policy.params
    assert "retrieval_mode" in policy.params


def test_build_policy_keeps_explicit_params() -> None:
    policy = build_retrieval_policy(
        "对比 DPO 和 PPO 的区别",
        profile="auto",
        explicit_params={"retrieval_mode": "dense", "top_k": 3},
    )

    assert policy.profile == "broad"
    assert policy.params["candidate_top_k"] >= 20
    assert "retrieval_mode" not in policy.params
    assert "top_k" not in policy.params


def test_build_policy_for_code_prefers_sparse_weight() -> None:
    policy = build_retrieval_policy("解释 train_step(batch) 的实现", profile="auto")

    assert policy.profile == "code"
    assert policy.params["retrieval_mode"] == "hybrid"
    assert policy.params["sparse_weight"] > policy.params["dense_weight"]
    assert policy.params["reranker"] == "keyword"
