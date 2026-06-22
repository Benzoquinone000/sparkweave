"""Lifecycle manager for enabled SparkBot channel adapters."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from sparkweave.services.sparkbot_support.channels import (
    SparkBotChannel,
    discover_builtin_channels,
)
from sparkweave.services.sparkbot_support.config_models import ChannelsConfig
from sparkweave.services.sparkbot_support.messages import SparkBotMessageBus

logger = logging.getLogger(__name__)

class SparkBotChannelManager:
    """Instantiate and manage enabled NG SparkBot channels."""

    def __init__(self, channels_config: ChannelsConfig, bus: SparkBotMessageBus) -> None:
        self.channels_config = channels_config
        self.bus = bus
        self.transcription_api_key = channels_config.transcription_api_key or os.environ.get(
            "GROQ_API_KEY", ""
        )
        self.channels: dict[str, SparkBotChannel] = {}
        self._init_channels()

    def _init_channels(self) -> None:
        for name, channel_cls in discover_builtin_channels().items():
            section = getattr(self.channels_config, name, None)
            if section is None or not getattr(section, "enabled", False):
                continue
            channel = channel_cls(section, self.bus)
            channel.transcription_api_key = self.transcription_api_key
            self.channels[name] = channel
        self._validate_allow_from()

    def _validate_allow_from(self) -> None:
        for name, channel in self.channels.items():
            allow_from = getattr(channel.config, "allow_from", None)
            if allow_from == []:
                raise ValueError(
                    f'Channel "{name}" has empty allow_from; use ["*"] or explicit ids.'
                )

    async def start_all(self) -> None:
        await asyncio.gather(
            *(channel.start() for channel in self.channels.values()),
            return_exceptions=True,
        )

    async def stop_all(self) -> None:
        for name, channel in self.channels.items():
            try:
                await channel.stop()
            except Exception:
                logger.exception("Error stopping SparkBot channel '%s'", name)

    def get_channel(self, name: str) -> SparkBotChannel | None:
        return self.channels.get(name)

    def get_status(self) -> dict[str, Any]:
        return {
            name: {"enabled": True, "running": channel.is_running}
            for name, channel in self.channels.items()
        }

    @property
    def enabled_channels(self) -> list[str]:
        return list(self.channels)

__all__ = ["SparkBotChannelManager"]
