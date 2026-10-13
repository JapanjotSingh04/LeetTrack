"""Tests for the demo-hardening settings: user cap, configurable rate limits, Argon2 tuning."""
from argon2 import PasswordHasher

import auth
from test_user_isolation import ORIGIN, PASSWORD, db, make_client, register  # noqa: F401


def _try_register(client, name):
    return client.post(
        "/api/auth/register",
        json={"username": name, "email": f"{name}@example.com", "password": PASSWORD},
        headers=ORIGIN,
    )


def test_no_cap_by_default(make_client, monkeypatch):
    monkeypatch.delenv("MAX_USERS", raising=False)
    for i in range(3):
        register(make_client(), f"user{i}")


def test_max_users_cap_blocks_extra_registrations(make_client, monkeypatch):
    monkeypatch.setenv("MAX_USERS", "2")
    register(make_client(), "capuser1")
    register(make_client(), "capuser2")
    blocked = _try_register(make_client(), "capuser3")
    assert blocked.status_code == 403
    assert "full" in blocked.json()["detail"].lower()


def test_register_rate_limits_can_be_raised_by_env(make_client, monkeypatch):
    monkeypatch.setenv("RATE_REGISTER_PER_IP", "8")
    monkeypatch.setenv("RATE_REGISTER_TOTAL", "50")
    codes = [_try_register(make_client(), f"burst{i}").status_code for i in range(7)]
    assert codes == [200] * 7


def test_default_register_limit_is_unchanged(make_client, monkeypatch):
    monkeypatch.delenv("RATE_REGISTER_PER_IP", raising=False)
    codes = [_try_register(make_client(), f"dflt{i}").status_code for i in range(6)]
    assert codes[:5] == [200] * 5 and codes[5] == 429


def test_argon2_uses_low_memory_settings_and_round_trips():
    assert auth._password_hasher.memory_cost <= 19456
    hashed = auth.hash_password("a-long-test-password")
    assert auth.verify_password("a-long-test-password", hashed)
    assert not auth.verify_password("wrong-password-value", hashed)


def test_hashes_made_with_old_default_settings_still_verify():
    legacy = PasswordHasher().hash("a-long-test-password")  # library defaults
    assert auth.verify_password("a-long-test-password", legacy)
