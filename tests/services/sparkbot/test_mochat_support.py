from __future__ import annotations

from sparkweave.services.sparkbot_support.config_models import (
    MochatConfig,
    MochatGroupRule,
)
from sparkweave.services.sparkbot_support.mochat import (
    MochatBufferedEntry,
    build_mochat_buffered_body,
    make_mochat_synthetic_event,
    normalize_mochat_content,
    parse_mochat_timestamp,
    resolve_mochat_require_mention,
    resolve_mochat_target,
    resolve_mochat_was_mentioned,
)


def test_resolve_mochat_target_distinguishes_sessions_and_panels() -> None:
    assert resolve_mochat_target("session_abc").is_panel is False
    assert resolve_mochat_target("panel:abc").is_panel is True
    assert resolve_mochat_target("abc").is_panel is True


def test_build_mochat_buffered_body_labels_group_messages() -> None:
    body = build_mochat_buffered_body(
        [
            MochatBufferedEntry(raw_body="hello", author="u1", sender_name="Ada"),
            MochatBufferedEntry(raw_body="world", author="u2", sender_username="linus"),
        ],
        is_group=True,
    )

    assert body == "Ada: hello\nlinus: world"


def test_resolve_mochat_mention_policy_prefers_group_rule() -> None:
    config = MochatConfig(groups={"group-1": MochatGroupRule(require_mention=False)})
    config.mention.require_in_groups = True

    assert resolve_mochat_require_mention(config, "session-1", "group-1") is False
    assert resolve_mochat_require_mention(config, "session-2", "group-2") is True


def test_mochat_payload_helpers_normalize_mentions_and_timestamp() -> None:
    event = make_mochat_synthetic_event(
        message_id="m1",
        author="u1",
        content={"text": "hi"},
        meta={"mentionIds": [{"id": "agent"}]},
        group_id="group",
        converse_id="panel",
        timestamp="2026-06-08T00:00:00Z",
    )

    payload = event["payload"]
    assert normalize_mochat_content(payload["content"]) == '{"text": "hi"}'
    assert resolve_mochat_was_mentioned(payload, "agent") is True
    assert parse_mochat_timestamp(event["timestamp"]) == 1780876800000
