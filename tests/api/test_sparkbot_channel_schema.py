"""Tests for the schema-driven channels endpoint helpers.

Covers:
* ``resolve_config_model``: maps each ``XxxChannel`` to its ``XxxConfig``.
* ``inline_refs``: flattens nested model ``$ref``s (slack ``dm`` subtree).
* ``collect_secret_fields``: only flags **string-typed** secret-looking keys
  (so e.g. ``user_token_read_only: bool`` is excluded).
* ``GET /api/v1/sparkbot/channels/schema`` integration: shape, snake_case
  property names, and that every migrated built-in channel survives the trip.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from sparkweave.api.routers._sparkbot_channel_schema import (
    all_channel_schemas,
    channel_schema_payload,
    collect_secret_fields,
    inline_refs,
    resolve_config_model,
)

EXPECTED_BUILTIN_CHANNELS = {
    "telegram",
    "slack",
    "discord",
    "dingtalk",
    "email",
    "feishu",
    "matrix",
    "mochat",
    "qq",
    "wecom",
    "whatsapp",
}


class TestResolveConfigModel:
    def test_telegram_pairs_with_telegram_config(self) -> None:
        from sparkweave.services.sparkbot import TelegramChannel, TelegramConfig

        assert resolve_config_model(TelegramChannel) is TelegramConfig

    def test_slack_pairs_with_slack_config(self) -> None:
        from sparkweave.services.sparkbot import SlackChannel, SlackConfig

        assert resolve_config_model(SlackChannel) is SlackConfig

    def test_discord_pairs_with_discord_config(self) -> None:
        from sparkweave.services.sparkbot import DiscordChannel, DiscordConfig

        assert resolve_config_model(DiscordChannel) is DiscordConfig

    def test_migrated_channels_pair_with_named_configs(self) -> None:
        from sparkweave.services import sparkbot

        for channel_name in EXPECTED_BUILTIN_CHANNELS:
            channel_cls = sparkbot.discover_builtin_channels()[channel_name]
            model = resolve_config_model(channel_cls)
            expected = channel_cls.__name__.replace("Channel", "") + "Config"
            assert model is getattr(sparkbot, expected)


class TestInlineRefs:
    def test_inlines_simple_def(self) -> None:
        schema = {
            "type": "object",
            "properties": {"dm": {"$ref": "#/$defs/SlackDMConfig"}},
            "$defs": {
                "SlackDMConfig": {
                    "type": "object",
                    "properties": {"enabled": {"type": "boolean"}},
                }
            },
        }
        out = inline_refs(schema)
        assert "$defs" not in out
        assert out["properties"]["dm"]["type"] == "object"
        assert out["properties"]["dm"]["properties"]["enabled"]["type"] == "boolean"

    def test_per_field_overrides_take_precedence(self) -> None:
        # Pydantic sometimes emits {"$ref": "...", "description": "..."}; the
        # description should override the referenced model's description.
        schema = {
            "type": "object",
            "properties": {
                "child": {"$ref": "#/$defs/Foo", "description": "override"},
            },
            "$defs": {
                "Foo": {"type": "object", "description": "original"},
            },
        }
        out = inline_refs(schema)
        assert out["properties"]["child"]["description"] == "override"


class TestCollectSecretFields:
    def test_flags_string_token_field(self) -> None:
        schema = {
            "properties": {
                "token": {"type": "string"},
                "enabled": {"type": "boolean"},
            }
        }
        assert collect_secret_fields(schema) == ["token"]

    def test_skips_boolean_with_secret_substring(self) -> None:
        # Slack's ``user_token_read_only`` is a flag, not a secret.
        schema = {
            "properties": {
                "user_token_read_only": {"type": "boolean"},
                "bot_token": {"type": "string"},
            }
        }
        assert collect_secret_fields(schema) == ["bot_token"]

    def test_walks_nested_objects(self) -> None:
        schema = {
            "properties": {
                "dm": {
                    "type": "object",
                    "properties": {"webhook_secret": {"type": "string"}},
                },
            }
        }
        assert collect_secret_fields(schema) == ["dm.webhook_secret"]

    def test_handles_nullable_strings(self) -> None:
        # Pydantic's ``Optional[str]`` becomes ``anyOf: [{type: string}, {type: null}]``.
        schema = {
            "properties": {
                "encrypt_key": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            }
        }
        assert collect_secret_fields(schema) == ["encrypt_key"]


class TestChannelSchemaPayload:
    def test_telegram_payload_shape(self) -> None:
        from sparkweave.services.sparkbot import TelegramChannel

        payload = channel_schema_payload(TelegramChannel)
        assert payload is not None
        assert payload["name"] == "telegram"
        assert payload["display_name"] == "Telegram"
        assert payload["secret_fields"] == ["token"]
        # Snake_case wire format (matches the storage form).
        props = payload["json_schema"]["properties"]
        assert "allow_from" in props and "allowFrom" not in props
        assert payload["default_config"]["enabled"] is False

    def test_slack_dm_subtree_inlined(self) -> None:
        from sparkweave.services.sparkbot import SlackChannel

        payload = channel_schema_payload(SlackChannel)
        assert payload is not None
        dm = payload["json_schema"]["properties"]["dm"]
        assert dm["type"] == "object"
        assert "enabled" in dm["properties"]
        # Bool flags whose names contain "token" must NOT be flagged secret.
        assert "user_token_read_only" not in payload["secret_fields"]
        assert "bot_token" in payload["secret_fields"]

    def test_migrated_channel_secret_fields(self) -> None:
        out = all_channel_schemas()

        assert out["dingtalk"]["secret_fields"] == ["client_secret"]
        assert out["email"]["secret_fields"] == ["imap_password", "smtp_password"]
        assert out["feishu"]["secret_fields"] == [
            "app_secret",
            "encrypt_key",
            "verification_token",
        ]
        assert out["matrix"]["secret_fields"] == ["access_token"]
        assert out["mochat"]["secret_fields"] == ["claw_token"]
        assert out["qq"]["secret_fields"] == ["secret"]
        assert out["wecom"]["secret_fields"] == ["secret"]
        assert out["whatsapp"]["secret_fields"] == ["bridge_token"]


class TestEndpoint:
    @pytest.fixture
    def client(self) -> TestClient:
        # Build a minimal FastAPI app with just the sparkbot router; the
        # ``/channels/schema`` endpoint doesn't touch the manager so no
        # fixturing of ``get_sparkbot_manager`` is needed.
        from fastapi import FastAPI

        from sparkweave.api.routers import sparkbot as sparkbot_router

        app = FastAPI()
        app.include_router(sparkbot_router.router, prefix="/api/v1/sparkbot")
        return TestClient(app)

    def test_returns_channels_and_global(self, client: TestClient) -> None:
        res = client.get("/api/v1/sparkbot/channels/schema")
        assert res.status_code == 200
        body = res.json()
        assert set(body.keys()) >= {"channels", "global"}
        assert set(body["channels"]) == EXPECTED_BUILTIN_CHANNELS

    def test_telegram_entry_has_secret_fields(self, client: TestClient) -> None:
        res = client.get("/api/v1/sparkbot/channels/schema")
        tg = res.json()["channels"]["telegram"]
        assert tg["secret_fields"] == ["token"]
        assert "token" in tg["json_schema"]["properties"]

    def test_global_schema_uses_snake_case(self, client: TestClient) -> None:
        res = client.get("/api/v1/sparkbot/channels/schema")
        global_payload = res.json()["global"]
        global_props = global_payload["json_schema"]["properties"]
        assert "send_progress" in global_props
        assert "send_tool_hints" in global_props
        assert "transcription_api_key" in global_props
        assert "sendProgress" not in global_props
        assert "email" not in global_props
        assert global_payload["secret_fields"] == ["transcription_api_key"]


class TestAllChannelSchemas:
    def test_returns_all_migrated_builtin_channels(self) -> None:
        out = all_channel_schemas()
        assert set(out) == EXPECTED_BUILTIN_CHANNELS
        # Every payload has the four documented keys.
        for entry in out.values():
            assert {
                "name",
                "display_name",
                "default_config",
                "secret_fields",
                "json_schema",
            } <= entry.keys()

