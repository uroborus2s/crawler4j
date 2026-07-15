#!/usr/bin/env python3
"""Build or publish workspace packages via one package-name-oriented wrapper."""

import argparse
import contextlib
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Sequence


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class BuildTarget:
    package: str
    dist_dir: Path


# Keep workspace build/publish order aligned with package dependencies.
BUILD_TARGETS = (
    BuildTarget("crawler4j-contracts", WORKSPACE_ROOT / "packages" / "crawler4j-contracts" / "dist"),
    BuildTarget("crawler4j-sdk", WORKSPACE_ROOT / "packages" / "crawler4j-sdk" / "dist"),
    BuildTarget("crawler4j", WORKSPACE_ROOT / "packages" / "crawler4j" / "dist"),
)
TARGETS_BY_PACKAGE = {target.package: target for target in BUILD_TARGETS}
SUPPORTED_ACTIONS = ("build", "publish")
PRESERVED_DIST_SUBDIRS = {
    "crawler4j": ("desktop",),
}


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


def publish_command(target: BuildTarget, *, dry_run: bool = False) -> list[str]:
    command = ["uv", "publish"]
    if dry_run:
        command.append("--dry-run")
    command.append(str(target.dist_dir / "*"))
    return command


def iter_targets(packages: Sequence[str] | None = None) -> list[BuildTarget]:
    if not packages:
        return list(BUILD_TARGETS)
    return [TARGETS_BY_PACKAGE[package] for package in packages]


def run_build(target: BuildTarget) -> None:
    command = build_command(target)
    print(f"[build] {target.package} -> {target.dist_dir}")
    print(f"[cmd]   {shlex.join(command)}")
    with _preserve_dist_subdirs(target):
        subprocess.run(command, cwd=WORKSPACE_ROOT, check=True)
    validate_build_output(target)


def validate_build_output(target: BuildTarget) -> None:
    preserved_names = PRESERVED_DIST_SUBDIRS.get(target.package, ())
    if not preserved_names:
        return

    sdists = sorted(target.dist_dir.glob("*.tar.gz"))
    if len(sdists) != 1:
        raise RuntimeError(f"expected one sdist for {target.package}, found {len(sdists)}")

    with tarfile.open(sdists[0], "r:gz") as archive:
        for member in archive.getmembers():
            parts = PurePosixPath(member.name).parts
            if any(name in parts for name in preserved_names):
                raise RuntimeError(
                    f"{target.package} sdist contains preserved desktop content: {member.name}"
                )


@contextlib.contextmanager
def _preserve_dist_subdirs(target: BuildTarget):
    names = PRESERVED_DIST_SUBDIRS.get(target.package, ())
    if not names:
        yield
        return

    preserved: list[tuple[Path, Path]] = []
    # Keep preserved desktop bundles outside the package root. Hatch includes live
    # project-root temporary directories in sdists, even when they only exist for
    # the duration of the build.
    with tempfile.TemporaryDirectory(dir=WORKSPACE_ROOT) as temp_dir:
        temp_root = Path(temp_dir)
        for name in names:
            source = target.dist_dir / name
            if not source.exists():
                continue
            destination = temp_root / name
            shutil.move(str(source), str(destination))
            preserved.append((destination, source))
        try:
            yield
        finally:
            for source, destination in preserved:
                if destination.exists():
                    shutil.rmtree(destination)
                shutil.move(str(source), str(destination))


def run_publish(target: BuildTarget, *, dry_run: bool = False) -> None:
    command = publish_command(target, dry_run=dry_run)
    print(f"[publish] {target.package} -> {target.dist_dir}")
    print(f"[cmd]     {shlex.join(command)}")
    subprocess.run(command, cwd=WORKSPACE_ROOT, check=True)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build or publish workspace packages using package names instead of raw uv dist paths.",
    )
    parser.add_argument(
        "items",
        nargs="*",
        metavar="ACTION_OR_PACKAGE",
        help=(
            "Optional action followed by package names. Supported actions: "
            "build, publish. If omitted, build is assumed."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Forward --dry-run to uv publish. Only valid with the publish action.",
    )
    args = parser.parse_args(argv)

    action = "build"
    items = list(args.items)
    if items and items[0] in SUPPORTED_ACTIONS:
        action = items.pop(0)

    invalid_packages = [item for item in items if item not in TARGETS_BY_PACKAGE]
    if invalid_packages:
        parser.error(
            "unknown package(s): "
            + ", ".join(invalid_packages)
            + ". Expected one of: "
            + ", ".join(TARGETS_BY_PACKAGE)
        )
    if args.dry_run and action != "publish":
        parser.error("--dry-run is only supported with the publish action")

    args.action = action
    args.packages = items
    return args


def build_main() -> int:
    return main(["build", *sys.argv[1:]])


def publish_main() -> int:
    return main(["publish", *sys.argv[1:]])


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    for target in iter_targets(args.packages):
        if args.action == "publish":
            run_publish(target, dry_run=args.dry_run)
            continue
        run_build(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
