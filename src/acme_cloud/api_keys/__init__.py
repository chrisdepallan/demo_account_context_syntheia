"""API keys, scopes, rate limits and webhooks for the Acme Cloud REST API.

Owned by the Identity team. Keys start with ``acme_live_`` or
``acme_test_``, are stored only as a SHA-256 hash plus the last 4
characters, and are limited to 25 active keys per workspace. See
``docs/reference/constants-and-glossary.md`` for every number.
"""

from acme_cloud.api_keys.models import ApiKey, KeyEnvironment, generate_key, hash_key
from acme_cloud.api_keys.rate_limit import RateLimiter, RateLimitStatus, requests_per_minute
from acme_cloud.api_keys.rotation import (
    EXPIRY_WARNING_DAYS, KEY_CACHE_TTL_SECONDS, ROTATION_GRACE_HOURS, KeyCache,
)
from acme_cloud.api_keys.scopes import ALL_SCOPES, has_scope, require_scope, validate_scopes
from acme_cloud.api_keys.service import (
    EXPIRY_CHOICES_DAYS, MAX_ACTIVE_KEYS_PER_WORKSPACE, ApiKeyService,
)
from acme_cloud.api_keys.webhooks import (
    WEBHOOK_EVENTS, WebhookEndpoint, WebhookRegistry, sign_payload, verify_signature,
)

__all__ = [
    "ALL_SCOPES", "ApiKey", "ApiKeyService", "EXPIRY_CHOICES_DAYS", "EXPIRY_WARNING_DAYS",
    "KEY_CACHE_TTL_SECONDS", "KeyCache", "KeyEnvironment", "MAX_ACTIVE_KEYS_PER_WORKSPACE",
    "ROTATION_GRACE_HOURS", "RateLimitStatus", "RateLimiter", "WEBHOOK_EVENTS",
    "WebhookEndpoint", "WebhookRegistry", "generate_key", "has_scope", "hash_key",
    "require_scope", "requests_per_minute", "sign_payload", "validate_scopes",
    "verify_signature",
]
