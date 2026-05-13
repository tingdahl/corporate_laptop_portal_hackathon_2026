from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path
from contextvars import ContextVar
from typing import Any

_request_file_hashes: ContextVar[tuple[str, ...]] = ContextVar("openrouter_mock_request_file_hashes", default=())


def is_enabled() -> bool:
    return os.getenv("OPENROUTER_MOCK_ENABLED", "0") == "1"


def fixture_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "testdata" / "openrouter_mock"


@lru_cache(maxsize=None)
def _load_fixture(name: str) -> dict[str, Any]:
    path = fixture_dir() / f"{name}_response.json"
    if not path.exists():
        raise FileNotFoundError(f"OpenRouter mock fixture not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _available_fixtures() -> list[str]:
    """List all available fixture names (user1, user2, etc.) in deterministic order."""
    fixtures = []
    for path in sorted(fixture_dir().glob("*_response.json")):
        name = path.stem.replace("_response", "")
        if name != "specs":  # Skip legacy single fixture
            fixtures.append(name)
    return fixtures or ["specs"]  # Fallback to legacy if no new fixtures


def set_request_file_hashes(file_hashes: list[str] | tuple[str, ...]) -> None:
    """Store the current request's source file hashes for mock fixture selection."""
    normalized = tuple(str(file_hash).strip().lower() for file_hash in file_hashes if str(file_hash).strip())
    _request_file_hashes.set(normalized)


def clear_request_file_hashes() -> None:
    """Clear request-scoped file hashes after a request completes."""
    _request_file_hashes.set(())


def _fixture_source_hashes(name: str) -> set[str]:
    payload = _load_fixture(name)
    hashes = payload.get("file_hashes", [])
    if isinstance(hashes, list) and hashes:
        return {str(file_hash).strip().lower() for file_hash in hashes if str(file_hash).strip()}
    return set()


def _match_fixture_by_files(request_file_hashes: tuple[str, ...]) -> str | None:
    if not request_file_hashes:
        return None

    request_set = {str(file_hash).strip().lower() for file_hash in request_file_hashes if str(file_hash).strip()}
    best_name: str | None = None
    best_score = 0

    for fixture_name in _available_fixtures():
        source_hashes = _fixture_source_hashes(fixture_name)
        score = len(request_set & source_hashes)
        if score > best_score:
            best_name = fixture_name
            best_score = score

    return best_name if best_score > 0 else None


def _select_fixture(seed: str = "") -> str:
    """
    Select a fixture deterministically based on a seed.
    Uses hash-based selection: same seed always returns same fixture,
    but different seeds get different fixtures.
    
    Strategy:
    - Use interpretation_id or upload hash as seed for deterministic-but-varied behavior
    - If no seed, use first available fixture
    """
    fixtures = _available_fixtures()
    if not fixtures:
        return "specs"

    request_files = _request_file_hashes.get()
    matched_fixture = _match_fixture_by_files(request_files)
    if matched_fixture:
        return matched_fixture
    
    if seed:
        # Hash the seed and use modulo to pick a fixture
        hash_val = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
        return fixtures[hash_val % len(fixtures)]
    return fixtures[0]


def _current_seed() -> str:
    """
    Get the seed for fixture selection.
    In a real scenario, this would use the interpretation_id,
    but since we don't have access to it here, we use a thread-local or env-based approach.
    For now, returns empty string (uses first fixture by default).
    """
    return os.getenv("OPENROUTER_MOCK_SEED", "")


def get_pii_boxes() -> list[dict[str, Any]]:
    fixture_name = _select_fixture(_current_seed())
    payload = _load_fixture(fixture_name)
    return list(payload.get("pii_detection", {}).get("boxes", []))


def get_interpretation() -> dict[str, Any]:
    fixture_name = _select_fixture(_current_seed())
    payload = _load_fixture(fixture_name)
    return dict(payload.get("interpretation", {}))


def available_fixtures() -> list[str]:
    """Public API to list all available mock fixtures."""
    return _available_fixtures()
