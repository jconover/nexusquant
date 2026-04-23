"""Session-level env fixture.

Any TestClient fires the app lifespan, which constructs AlpacaSettings
from env. Tests that don't care about real keys -- most of them -- get
valid-shape placeholders from this autouse fixture. Tests that do care
(test_settings_validation.py) override inside their own monkeypatch.

When RUN_ALPACA_INTEGRATION=1 is set, the fixture steps aside so the
integration tests read whatever ALPACA_* is in the real environment
(typically loaded from .env at the repo root).
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

ALPACA_TEST_ENV = {
    "ALPACA_API_KEY_ID": "PK_test_placeholder_key",
    "ALPACA_API_SECRET_KEY": "sk_test_placeholder_secret",
    "ALPACA_PAPER": "true",
    "ALPACA_BASE_URL": "https://paper-api.alpaca.markets",
    "ALPACA_DATA_FEED": "iex",
}


@pytest.fixture(autouse=True)
def _alpaca_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    if os.environ.get("RUN_ALPACA_INTEGRATION"):
        yield
        return
    for k, v in ALPACA_TEST_ENV.items():
        monkeypatch.setenv(k, v)
    yield
