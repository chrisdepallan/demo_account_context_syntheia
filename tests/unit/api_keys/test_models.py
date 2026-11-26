"""ApiKey model: prefixes, 32-character secret, SHA-256 hash and last 4 only."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from acme_cloud.api_keys import models
from acme_cloud.api_keys.models import (
    ApiKey, KeyEnvironment, generate_key, hash_key, is_well_formed,
)

NOW = datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc)


def make_key(**overrides) -> ApiKey:
    full_key = generate_key(KeyEnvironment.TEST)
    values = dict(
        id="key_TEST0001", workspace_id="ws_TEST01", account_id="acc_TEST0001", name="CI",
        prefix=models.TEST_PREFIX, key_hash=hash_key(full_key), last4=full_key[-4:],
        scopes=frozenset({"projects:read"}), created_by="usr_OWNER001", created_at=NOW,
    )
    values.update(overrides)
    return ApiKey(**values)


@pytest.mark.parametrize("environment, prefix", [
    (KeyEnvironment.LIVE, "acme_live_"), (KeyEnvironment.TEST, "acme_test_"),
])
def test_keys_have_the_environment_prefix_and_a_32_character_secret(environment, prefix):
    full_key = generate_key(environment)
    assert full_key.startswith(prefix)
    assert len(full_key) == len(prefix) + 32
    assert full_key[len(prefix):].isalnum()
    assert is_well_formed(full_key)


def test_generated_keys_are_unique():
    assert len({generate_key() for _ in range(200)}) == 200


@pytest.mark.parametrize("candidate", [
    "acme_live_tooshort",
    "acme_prod_" + "A" * 32,
    "acme_test_" + "A" * 33,
    "acme_test_" + "A" * 31 + "-",
    "",
])
def test_malformed_keys_are_recognised(candidate):
    assert not is_well_formed(candidate)


def test_hash_is_a_sha256_hex_digest_and_is_stable():
    example = "acme_test_EXAMPLEEXAMPLEEXAMPLEEXAMPLE0000"
    assert len(hash_key(example)) == 64
    assert hash_key(example) == hash_key(example)
    assert hash_key(example) != hash_key(example[:-1] + "1")


def test_stored_key_shows_only_prefix_and_last_4():
    key = make_key(last4="0000")
    assert key.masked == "acme_test_...0000"
    assert key.environment is KeyEnvironment.TEST
    assert not hasattr(key, "full_key") and not hasattr(key, "secret")


def test_key_without_expiry_never_expires():
    key = make_key(expires_at=None)
    assert not key.is_expired(NOW + timedelta(days=3650))
    assert key.is_usable(NOW + timedelta(days=3650))


def test_key_expires_at_its_expiry_time():
    key = make_key(expires_at=NOW + timedelta(days=30))
    assert key.is_usable(NOW + timedelta(days=30) - timedelta(seconds=1))
    assert not key.is_usable(NOW + timedelta(days=30))


def test_revoked_key_is_not_usable_and_not_active():
    key = make_key(revoked_at=NOW)
    assert not key.is_usable(NOW)
    assert not key.counts_as_active(NOW)


def test_rotated_key_is_usable_only_during_its_grace_period():
    key = make_key(rotated_at=NOW, grace_ends_at=NOW + timedelta(hours=24),
                   replaced_by="key_TEST0002")
    assert key.is_usable(NOW + timedelta(hours=23, minutes=59))
    assert not key.is_usable(NOW + timedelta(hours=24))
    # A rotated-out key does not use one of the 25 active-key slots.
    assert not key.counts_as_active(NOW)


def test_plain_key_counts_as_active():
    assert make_key().counts_as_active(NOW)
    assert not make_key(expires_at=NOW).counts_as_active(NOW)
