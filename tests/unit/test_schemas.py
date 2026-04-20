"""Validate every MCP tool schema and its example payloads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from jsonschema.validators import validator_for

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = REPO_ROOT / "schemas"
EXAMPLES_DIR = SCHEMAS_DIR / "examples"

TOOLS = [
    "get_market_status",
    "get_watchlist",
    "get_signal",
    "get_sentiment",
    "get_portfolio",
    "get_risk_budget",
    "place_paper_order",
]


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _tool_doc(tool: str) -> dict[str, Any]:
    doc = _load_json(SCHEMAS_DIR / f"{tool}.json")
    assert isinstance(doc, dict)
    return doc


def _example_cases() -> list[tuple[str, str, Path]]:
    """Return (tool, kind, example_path) for every example file."""
    cases: list[tuple[str, str, Path]] = []
    for tool in TOOLS:
        cases.extend(
            (tool, "request", p) for p in sorted(EXAMPLES_DIR.glob(f"{tool}.request*.json"))
        )
        cases.extend(
            (tool, "response", p) for p in sorted(EXAMPLES_DIR.glob(f"{tool}.response*.json"))
        )
    return cases


@pytest.mark.parametrize("tool", TOOLS)
def test_schema_is_valid_draft_2020_12(tool: str) -> None:
    doc = _tool_doc(tool)
    assert "request" in doc and "response" in doc
    Draft202012Validator.check_schema(doc["request"])
    Draft202012Validator.check_schema(doc["response"])


@pytest.mark.parametrize("tool", TOOLS)
def test_canonical_example_pair_present(tool: str) -> None:
    assert (EXAMPLES_DIR / f"{tool}.request.json").is_file()
    assert (EXAMPLES_DIR / f"{tool}.response.json").is_file()


@pytest.mark.parametrize(
    ("tool", "kind", "example_path"),
    _example_cases(),
    ids=[f"{t}-{k}-{p.stem}" for t, k, p in _example_cases()],
)
def test_example_validates_against_schema(tool: str, kind: str, example_path: Path) -> None:
    doc = _tool_doc(tool)
    schema = doc[kind]
    instance = _load_json(example_path)
    cls = validator_for(schema, default=Draft202012Validator)
    validator = cls(schema, format_checker=cls.FORMAT_CHECKER)
    validator.validate(instance)


def test_place_paper_order_response_covers_all_outcomes() -> None:
    """All three oneOf branches have at least one example."""
    statuses = set()
    for path in EXAMPLES_DIR.glob("place_paper_order.response*.json"):
        payload = _load_json(path)
        statuses.add(payload["status"])
    assert statuses == {"executed", "pending_approval", "rejected"}
