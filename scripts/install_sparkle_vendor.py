#!/usr/bin/env python3
"""Install a Sparkle distribution into the repository's vendor directory."""

from __future__ import annotations

import argparse
import shutil
import tempfile
from contextlib import nullcontext
from pathlib import Path

from scripts.package_macos_internal_release import DEFAULT_SPARKLE_ROOT


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install Sparkle into packages/crawler4j/vendor/macos/sparkle.")
    parser.add_argument(
        "--archive",
        type=Path,
        help="Path to a Sparkle release archive (.tar.xz/.tar.gz/.zip).",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        help="Path to an already extracted Sparkle distribution directory.",
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=DEFAULT_SPARKLE_ROOT,
        help=f"Install target directory (default: {DEFAULT_SPARKLE_ROOT}).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace the existing target directory if it already exists.",
    )
    return parser.parse_args(argv)


def validate_args(args: argparse.Namespace) -> None:
    if bool(args.archive) == bool(args.source_dir):
        raise ValueError("请二选一提供 --archive 或 --source-dir。")


def _candidate_root(path: Path) -> bool:
    return (path / "Sparkle.framework").exists() and (path / "bin" / "generate_appcast").exists()


def locate_distribution_root(path: Path) -> Path:
    root = path.resolve()
    if _candidate_root(root):
        return root

    for framework_path in sorted(root.rglob("Sparkle.framework")):
        candidate = framework_path.parent
        if _candidate_root(candidate):
            return candidate

    raise FileNotFoundError(f"未在 {path} 中找到包含 Sparkle.framework 和 bin/generate_appcast 的 Sparkle 分发目录。")


def extract_archive(archive_path: Path, extract_root: Path) -> Path:
    archive = archive_path.expanduser().resolve()
    if not archive.exists():
        raise FileNotFoundError(f"未找到 Sparkle 压缩包: {archive}")

    shutil.unpack_archive(str(archive), str(extract_root))
    return locate_distribution_root(extract_root)


def install_distribution(source_root: Path, target_dir: Path, *, force: bool) -> Path:
    source = source_root.resolve()
    target = target_dir.expanduser().resolve()

    if target.exists():
        if not force:
            raise FileExistsError(f"目标目录已存在: {target}。若需覆盖，请追加 --force。")
        shutil.rmtree(target)

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, symlinks=True)
    return target


def resolve_source_root(args: argparse.Namespace) -> Path:
    validate_args(args)
    if args.source_dir:
        source_dir = args.source_dir.expanduser().resolve()
        if not source_dir.exists():
            raise FileNotFoundError(f"未找到 Sparkle 目录: {source_dir}")
        return locate_distribution_root(source_dir)
    raise AssertionError("archive sources must be resolved inside the extraction context")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    validate_args(args)
    temp_context = tempfile.TemporaryDirectory(prefix="crawler4j-sparkle-") if args.archive else nullcontext()

    with temp_context as temp_root:
        if args.archive:
            assert temp_root is not None
            source_root = extract_archive(args.archive, Path(temp_root))
        else:
            source_root = resolve_source_root(args)

        target_dir = install_distribution(source_root, args.target_dir, force=args.force)

    print(f"[sparkle] installed to {target_dir}")
    print(f"[framework] {target_dir / 'Sparkle.framework'}")
    print(f"[generate_appcast] {target_dir / 'bin' / 'generate_appcast'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
