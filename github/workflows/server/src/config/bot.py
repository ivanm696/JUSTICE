"""Bot configuration helpers.

This module provides a small, well-documented configuration helper for the bot
used by the server workflow. It reads required values from environment
variables and validates presence of the bot token.

Conventions:
- Uses Python dataclasses
- Raises a clear error when required env var is missing
- Keeps behaviour deterministic and easy to test
"""

from dataclasses import dataclass
import os
from typing import Optional


@dataclass(frozen=True)
class BotConfig:
    """Immutable configuration for the bot.

    Attributes:
        token: Bot token (required).
        webhook_url: Optional webhook URL for receiving events.
        debug: Whether debug mode is enabled.
    """

    token: str
    webhook_url: Optional[str] = None
    debug: bool = False


def load_bot_config() -> BotConfig:
    """Load and validate bot configuration from environment variables.

    Required environment variables:
        - BOT_TOKEN

    Optional environment variables:
        - BOT_WEBHOOK_URL
        - BOT_DEBUG ("1", "true", "yes" to enable)
    """
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Environment variable BOT_TOKEN is required for bot configuration")

    webhook = os.getenv("BOT_WEBHOOK_URL")
    debug = os.getenv("BOT_DEBUG", "false").lower() in ("1", "true", "yes")

    return BotConfig(token=token, webhook_url=webhook, debug=debug)


__all__ = ["BotConfig", "load_bot_config"]
