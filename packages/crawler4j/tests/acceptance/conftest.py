from __future__ import annotations

from pathlib import Path

import pytest

from ._helpers import build_package, enrich_module, scaffold_module


@pytest.fixture
def module_root(tmp_path: Path) -> Path:
    return scaffold_module(tmp_path)


@pytest.fixture
def rich_module_root(module_root: Path) -> Path:
    return enrich_module(module_root)


@pytest.fixture
def built_archive(rich_module_root: Path) -> Path:
    return build_package(rich_module_root)


@pytest.fixture
def host_home(tmp_path: Path) -> Path:
    home = tmp_path / "host-home"
    home.mkdir()
    return home
