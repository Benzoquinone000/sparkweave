from sparkweave.api.routers._sparkbot_channel_schema import resolve_config_model
from sparkweave.services import sparkbot as sparkbot_module
from sparkweave.services.sparkbot_support import channels
from sparkweave.services.sparkbot_support.channel_manager import SparkBotChannelManager


def test_sparkbot_reexports_channel_adapters_for_compatibility() -> None:
    assert sparkbot_module.TelegramChannel is channels.TelegramChannel
    assert sparkbot_module.discover_builtin_channels()["telegram"] is channels.TelegramChannel
    assert sparkbot_module.SparkBotChannelManager is SparkBotChannelManager


def test_channel_module_keeps_config_models_for_schema_reflection() -> None:
    assert resolve_config_model(channels.TelegramChannel) is channels.TelegramConfig
