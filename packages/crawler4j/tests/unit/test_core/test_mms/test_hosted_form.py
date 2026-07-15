from __future__ import annotations

import pytest

from src.core.mms.ui.hosted_form import (
    FORM_EVENT_STALE,
    FORM_HANDLE_REJECTED,
    FORM_INITIAL_VALUES_INVALID,
    FORM_SCOPE_UNAVAILABLE,
    HostedFormController,
    HostedFormOwnerScope,
    HostedFormRegistry,
    HostedFormUnavailableTools,
)


def _controller(applied: list[dict[str, object]]) -> HostedFormController:
    return HostedFormController(
        mode="create",
        field_names=("priority", "enabled", "note", "marker"),
        initial_values={"priority": 1, "enabled": True, "note": "old", "marker": "value"},
        apply_values=lambda values: applied.append(dict(values)),
    )


def test_hosted_form_reset_preserves_falsy_values_and_clears_state():
    applied: list[dict[str, object]] = []
    controller = _controller(applied)
    change = controller.change("priority", 2)
    controller.set_validation_error("note", "invalid")

    assert change.previous_value == 1
    assert change.value == 2
    assert change.values["priority"] == 2
    assert controller.dirty is True
    assert controller.validation_errors == {"note": "invalid"}

    controller.reset(
        {
            "priority": 0,
            "enabled": False,
            "note": "",
            "marker": "undefined",
        }
    )

    expected = {"priority": 0, "enabled": False, "note": "", "marker": "undefined"}
    assert applied == [expected]
    assert controller.values == expected
    assert controller.initial_values == expected
    assert controller.dirty is False
    assert controller.validation_errors == {}


def test_hosted_form_reset_rejects_unknown_fields_without_mutation():
    applied: list[dict[str, object]] = []
    controller = _controller(applied)
    before = controller.values

    with pytest.raises(RuntimeError, match=FORM_INITIAL_VALUES_INVALID):
        controller.reset({"priority": 0, "unknown": "value"})

    assert controller.values == before
    assert applied == []


def test_hosted_form_dirty_comparison_is_type_sensitive_for_falsy_values():
    controller = _controller([])
    controller.reset({"priority": 0, "enabled": False, "note": "", "marker": "undefined"})

    controller.change("priority", False)

    assert controller.dirty is True


def test_hosted_form_registry_rejects_closed_expired_forged_and_forbidden_handles():
    now = [10.0]
    registry = HostedFormRegistry(ttl_seconds=5.0, clock=lambda: now[0])
    owner = HostedFormOwnerScope(module_name="demo", page_id="accounts", session_id="session-a")
    forbidden_owner = HostedFormOwnerScope(module_name="demo", page_id="accounts", session_id="session-b")
    controller = _controller([])
    form_id = registry.open_form(owner, controller)
    bound = registry.bind_tools(owner, form_id=form_id, revision=controller.revision)

    with pytest.raises(RuntimeError, match=FORM_HANDLE_REJECTED):
        bound.reset(form_id="forged", initial_values=controller.values)
    with pytest.raises(RuntimeError, match=FORM_HANDLE_REJECTED):
        registry.bind_tools(forbidden_owner, form_id=form_id, revision=controller.revision).reset(
            form_id=form_id,
            initial_values=controller.values,
        )

    now[0] = 16.0
    with pytest.raises(RuntimeError, match=FORM_HANDLE_REJECTED):
        bound.reset(form_id=form_id, initial_values=controller.values)

    now[0] = 20.0
    controller = _controller([])
    form_id = registry.open_form(owner, controller)
    bound = registry.bind_tools(owner, form_id=form_id, revision=controller.revision)
    registry.close_form(form_id)
    with pytest.raises(RuntimeError, match=FORM_HANDLE_REJECTED):
        bound.reset(form_id=form_id, initial_values=controller.values)


@pytest.mark.parametrize(
    "forbidden_owner",
    [
        HostedFormOwnerScope(module_name="other", page_id="accounts", session_id="session-a"),
        HostedFormOwnerScope(module_name="demo", page_id="other", session_id="session-a"),
        HostedFormOwnerScope(module_name="demo", page_id="accounts", session_id="session-b"),
    ],
)
def test_hosted_form_registry_binds_module_page_and_session(forbidden_owner):
    registry = HostedFormRegistry()
    owner = HostedFormOwnerScope(module_name="demo", page_id="accounts", session_id="session-a")
    controller = _controller([])
    form_id = registry.open_form(owner, controller)

    with pytest.raises(RuntimeError, match=FORM_HANDLE_REJECTED):
        registry.bind_tools(forbidden_owner, form_id=form_id, revision=controller.revision).reset(
            form_id=form_id,
            initial_values=controller.values,
        )

def test_hosted_form_registry_rejects_stale_event_revision():
    registry = HostedFormRegistry()
    owner = HostedFormOwnerScope(module_name="demo", page_id="accounts", session_id="session-a")
    controller = _controller([])
    form_id = registry.open_form(owner, controller)
    old_tools = registry.bind_tools(owner, form_id=form_id, revision=controller.revision)
    controller.change("priority", 2)

    with pytest.raises(RuntimeError, match=FORM_EVENT_STALE):
        old_tools.reset(form_id=form_id, initial_values=controller.values)


def test_hosted_form_registry_rejects_handle_when_form_is_no_longer_open():
    registry = HostedFormRegistry()
    owner = HostedFormOwnerScope(module_name="demo", page_id="accounts", session_id="session-a")
    controller = _controller([])
    open_state = [True]
    form_id = registry.open_form(owner, controller, is_open=lambda: open_state[0])
    bound = registry.bind_tools(owner, form_id=form_id, revision=controller.revision)

    open_state[0] = False

    with pytest.raises(RuntimeError, match=FORM_HANDLE_REJECTED):
        bound.reset(form_id=form_id, initial_values=controller.values)


def test_hosted_form_unavailable_tools_reject_reset():
    with pytest.raises(RuntimeError, match=FORM_SCOPE_UNAVAILABLE):
        HostedFormUnavailableTools().reset(form_id="any", initial_values={})
