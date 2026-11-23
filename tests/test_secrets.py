"""API keys never leak: masking works and the key file is ignored by git.

These tests use a made-up key, never a real one, and never the API.
"""

from pathlib import Path

import common

ROOT = Path(__file__).resolve().parent.parent
FAKE = "11111111-2222-3333-4444-555555555555"


def test_mask_hides_a_known_key():
    text = f"key is {FAKE} here"
    assert FAKE not in common.mask(text, secrets=[FAKE])


def test_mask_hides_key_in_entsoe_url_even_if_unknown():
    url = f"https://web-api.tp.entsoe.eu/api?securityToken={FAKE}&documentType=A44"
    masked = common.mask(url, secrets=[])
    assert FAKE not in masked
    assert "securityToken=***&documentType=A44" in masked


def test_mask_hides_header_style_key():
    text = f"headers={{'x-api-key': '{FAKE}'}}"
    assert FAKE not in common.mask(text, secrets=[])


def test_read_secret_from_a_temporary_env_file(tmp_path):
    env = tmp_path / ".env"
    env.write_text(f"ENTSOE_API_KEY={FAKE}\n", encoding="utf-8")
    assert common.read_secret("ENTSOE_API_KEY", env) == FAKE
    assert common.read_secret("FINGRID_API_KEY", env) is None


def test_placeholder_does_not_count_as_a_key(tmp_path):
    env = tmp_path / ".env"
    env.write_text("ENTSOE_API_KEY=your-token-here\n", encoding="utf-8")
    assert common.read_secret("ENTSOE_API_KEY", env) is None


def test_env_file_is_ignored_by_git():
    lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in lines


def test_env_example_holds_only_a_placeholder():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "ENTSOE_API_KEY=your-token-here" in text
