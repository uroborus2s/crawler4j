#!/usr/bin/env python3
"""Build publishable workspace packages into their package-local dist directories."""

import argparse
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class BuildTarget:
    package: str
    dist_dir: Path


BUILD_TARGETS = (
    BuildTarget("crawler4j-sdk", WORKSPACE_ROOT / "packages" / "crawler4j-sdk" / "dist"),
    BuildTarget("crawler4j", WORKSPACE_ROOT / "packages" / "crawler4j" / "dist"),
    BuildTarget("crawler4j-contracts", WORKSPACE_ROOT / "packages" / "crawler4j-contracts" / "dist"),
)
TARGETS_BY_PACKAGE = {target.package: target for target in BUILD_TARGETS}


def build_command(target: BuildTarget) -> list[str]:
    return [
        "uv",
        "build",
        "--package",
        target.package,
        "--out-dir",
        str(target.dist_dir),
        "--clear",
    ]


def iter_targets(packages: Sequence[str] | None = None) -> list[BuildTarget]:
    if not packages:
        return list(BUILD_TARGETS)
    return [TARGETS_BY_PACKAGE[package] for package in packages]


def run_build(target: BuildTarget) -> None:
    command = build_command(target)
    print(f"[build] {target.package} -> {target.dist_dir}")
    print(f"[cmd]   {shlex.join(command)}")
    subprocess.run(command, cwd=WORKSPACE_ROOT, check=True)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build workspace packages into their package-local dist directories.",
    )
    parser.add_argument(
        "packages",
        nargs="*",
        choices=[target.package for target in BUILD_TARGETS],
        metavar="PACKAGE",
        help="Optional subset of workspace packages to build. Defaults to all publishable packages.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    for target in iter_targets(args.packages):
        run_build(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
