"""Tests for application behavior."""

import pytest

from app.config import Settings
from app.services.access import AccessPolicy


def test_configured_offer_restriction():
    policy = AccessPolicy(Settings(offer_creation_enabled=False, _env_file=None))
    assert not policy.can_create("offer")
    assert policy.can_create("group")
    with pytest.raises(PermissionError, match="администратору"):
        policy.require_create("offer")


def test_real_forbidden_is_remembered():
    policy = AccessPolicy(Settings(offer_creation_enabled=True, _env_file=None))
    policy.deny("unknown")
    assert policy.denied == set()
    policy.deny("group")
    assert not policy.creation_rights()["group"]
    assert policy.creation_rights()["offer"]
