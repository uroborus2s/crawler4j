"""SDK hosted_ui compatibility re-export regression tests."""

from __future__ import annotations

import crawler4j_contracts.hosted_ui as contracts_hosted_ui
import crawler4j_sdk.hosted_ui as sdk_hosted_ui


def test_sdk_hosted_ui_reexports_contracts_public_symbols():
    public_names = [name for name in dir(contracts_hosted_ui) if not name.startswith("_")]

    assert set(sdk_hosted_ui.__all__) == set(public_names)
    for name in public_names:
        assert getattr(sdk_hosted_ui, name) is getattr(contracts_hosted_ui, name)


def test_sdk_hosted_ui_proxies_private_helpers():
    assert sdk_hosted_ui._validate_managed_identifier is contracts_hosted_ui._validate_managed_identifier
    assert "_validate_managed_identifier" in dir(sdk_hosted_ui)
