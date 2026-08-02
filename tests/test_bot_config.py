import importlib.util
import os
import uuid


def _load_bot_module():
    """Dynamically load the bot config module from the repository path.

    Uses a unique module name per call to avoid import caching between tests.
    """
    repo_root = os.getcwd()
    path = os.path.join(repo_root, "github", "workflows", "server", "src", "config", "bot.py")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Bot module not found at {path}")

    spec = importlib.util.spec_from_file_location(f"bot_mod_{uuid.uuid4().hex}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_bot_config_success(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "secret-token")
    monkeypatch.setenv("BOT_WEBHOOK_URL", "https://example.com/hook")
    monkeypatch.setenv("BOT_DEBUG", "1")

    bot_mod = _load_bot_module()
    cfg = bot_mod.load_bot_config()

    assert cfg.token == "secret-token"
    assert cfg.webhook_url == "https://example.com/hook"
    assert cfg.debug is True


def test_load_bot_config_missing_token(monkeypatch):
    # Ensure BOT_TOKEN is not set
    monkeypatch.delenv("BOT_TOKEN", raising=False)

    bot_mod = _load_bot_module()
    import pytest

    with pytest.raises(RuntimeError):
        bot_mod.load_bot_config()
