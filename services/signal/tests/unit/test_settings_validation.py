from __future__ import annotations

import pytest
from nexusquant_signal.config import AlpacaSettings
from pydantic import ValidationError


def _set_env(monkeypatch: pytest.MonkeyPatch, **kwargs: str) -> None:
    """Set ALPACA_ env vars and delete any we didn't set so the run is hermetic."""
    keys = {
        "ALPACA_API_KEY_ID",
        "ALPACA_API_SECRET_KEY",
        "ALPACA_PAPER",
        "ALPACA_BASE_URL",
        "ALPACA_DATA_FEED",
    }
    for k in keys:
        monkeypatch.delenv(k, raising=False)
    for k, v in kwargs.items():
        monkeypatch.setenv(k, v)


def test_missing_required_fields_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(monkeypatch)
    with pytest.raises(ValidationError):
        AlpacaSettings(_env_file=None)  # type: ignore[call-arg]


def test_happy_path_paper_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(
        monkeypatch,
        ALPACA_API_KEY_ID="k",
        ALPACA_API_SECRET_KEY="s",
        ALPACA_PAPER="true",
        ALPACA_BASE_URL="https://paper-api.alpaca.markets",
    )
    s = AlpacaSettings(_env_file=None)  # type: ignore[call-arg]
    assert s.paper is True
    assert s.base_url == "https://paper-api.alpaca.markets"
    assert s.data_feed == "iex"


def test_paper_false_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(
        monkeypatch,
        ALPACA_API_KEY_ID="k",
        ALPACA_API_SECRET_KEY="s",
        ALPACA_PAPER="false",
        ALPACA_BASE_URL="https://paper-api.alpaca.markets",
    )
    with pytest.raises(ValidationError, match="paper"):
        AlpacaSettings(_env_file=None)  # type: ignore[call-arg]


def test_live_base_url_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(
        monkeypatch,
        ALPACA_API_KEY_ID="k",
        ALPACA_API_SECRET_KEY="s",
        ALPACA_PAPER="true",
        ALPACA_BASE_URL="https://api.alpaca.markets",
    )
    with pytest.raises(ValidationError, match=r"[Ll]ive trading URL"):
        AlpacaSettings(_env_file=None)  # type: ignore[call-arg]


def test_arbitrary_non_paper_url_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(
        monkeypatch,
        ALPACA_API_KEY_ID="k",
        ALPACA_API_SECRET_KEY="s",
        ALPACA_PAPER="true",
        ALPACA_BASE_URL="https://example.com",
    )
    with pytest.raises(ValidationError, match=r"paper-api\.alpaca\.markets"):
        AlpacaSettings(_env_file=None)  # type: ignore[call-arg]


def test_empty_api_key_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(
        monkeypatch,
        ALPACA_API_KEY_ID="",
        ALPACA_API_SECRET_KEY="s",
        ALPACA_PAPER="true",
        ALPACA_BASE_URL="https://paper-api.alpaca.markets",
    )
    with pytest.raises(ValidationError):
        AlpacaSettings(_env_file=None)  # type: ignore[call-arg]
