from __future__ import annotations

from pathlib import Path

import pytest

from ._helpers import ACCEPTANCE_GATE_MATRIX, AcceptanceGateCommand, run_cli


def test_acceptance_gate_matrix_orders_progressively():
    assert [item.name for item in ACCEPTANCE_GATE_MATRIX] == [
        "structure",
        "release",
        "full",
        "package_verify",
    ]


@pytest.mark.parametrize(
    "gate_command",
    [item for item in ACCEPTANCE_GATE_MATRIX if not item.needs_archive],
    ids=lambda item: item.name,
)
def test_acceptance_gate_module_checks_pass(
    rich_module_root: Path,
    gate_command: AcceptanceGateCommand,
):
    result = run_cli(*gate_command.argv, cwd=rich_module_root)
    result.assert_ok()
    result.assert_stdout_contains(gate_command.success_text)


@pytest.mark.parametrize(
    "gate_command",
    [item for item in ACCEPTANCE_GATE_MATRIX if item.needs_archive],
    ids=lambda item: item.name,
)
def test_acceptance_gate_archive_checks_pass(
    rich_module_root: Path,
    built_archive: Path,
    gate_command: AcceptanceGateCommand,
):
    result = run_cli(*gate_command.argv, str(built_archive), cwd=rich_module_root)
    result.assert_ok()
    result.assert_stdout_contains(gate_command.success_text)
