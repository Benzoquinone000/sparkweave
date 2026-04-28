from __future__ import annotations

from sparkweave.runtime.policy import capability_enabled_by_default, select_runtime


def test_policy_defaults_migrated_capabilities_to_langgraph(monkeypatch):
    monkeypatch.delenv("SPARKWEAVE_RUNTIME", raising=False)
    monkeypatch.delenv("SPARKWEAVE_NG_DEFAULT_CAPABILITIES", raising=False)

    assert select_runtime(capability="chat") == "langgraph"
    assert select_runtime(capability="custom_plugin") == "legacy"


def test_policy_explicit_langgraph_wins_over_legacy_env(monkeypatch):
    monkeypatch.setenv("SPARKWEAVE_RUNTIME", "legacy")

    assert select_runtime(capability="chat", explicit_runtime="ng") == "langgraph"


def test_policy_explicit_legacy_wins_over_langgraph_env(monkeypatch):
    monkeypatch.setenv("SPARKWEAVE_RUNTIME", "ng")

    assert select_runtime(capability="chat", explicit_runtime="legacy") == "legacy"


def test_policy_accepts_compatibility_runtime_aliases(monkeypatch):
    monkeypatch.setenv("SPARKWEAVE_RUNTIME", "ng")

    assert select_runtime(capability="chat", explicit_runtime="compatibility") == "legacy"
    assert select_runtime(capability="chat", explicit_runtime="compat") == "legacy"
    assert select_runtime(capability="chat", env_runtime="compatibility") == "legacy"
    assert capability_enabled_by_default("chat", default_capabilities="compatibility") is False


def test_policy_explicit_default_uses_ng_default_for_migrated_capability(monkeypatch):
    monkeypatch.setenv("SPARKWEAVE_RUNTIME", "legacy")

    assert select_runtime(capability="chat", explicit_runtime="default") == "langgraph"
    assert select_runtime(capability="custom_plugin", explicit_runtime="default") == "legacy"


def test_policy_auto_uses_capability_allowlist(monkeypatch):
    monkeypatch.setenv("SPARKWEAVE_RUNTIME", "auto")
    monkeypatch.setenv("SPARKWEAVE_NG_DEFAULT_CAPABILITIES", "chat,deep_solve")

    assert select_runtime(capability="chat") == "langgraph"
    assert select_runtime(capability="deep_solve") == "langgraph"
    assert select_runtime(capability="visualize") == "legacy"


def test_policy_auto_all_is_limited_to_migrated_capabilities(monkeypatch):
    monkeypatch.setenv("SPARKWEAVE_RUNTIME", "auto")
    monkeypatch.setenv("SPARKWEAVE_NG_DEFAULT_CAPABILITIES", "all")

    assert select_runtime(capability="math_animator") == "langgraph"
    assert select_runtime(capability="custom_plugin") == "legacy"


def test_policy_auto_without_allowlist_uses_migrated_defaults(monkeypatch):
    monkeypatch.setenv("SPARKWEAVE_RUNTIME", "auto")
    monkeypatch.delenv("SPARKWEAVE_NG_DEFAULT_CAPABILITIES", raising=False)

    assert select_runtime(capability="chat") == "langgraph"
    assert select_runtime(capability="custom_plugin") == "legacy"


def test_capability_enabled_by_default_parses_allowlist_values(monkeypatch):
    monkeypatch.setenv("SPARKWEAVE_NG_DEFAULT_CAPABILITIES", "chat, visualize")

    assert capability_enabled_by_default("chat") is True
    assert capability_enabled_by_default("visualize") is True
    assert capability_enabled_by_default("deep_question") is False



