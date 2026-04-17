"""Semantic-version helpers for module manifests and upgrades."""

from __future__ import annotations

import re
from dataclasses import dataclass


SEMVER_RE = re.compile(
    r"^v?"
    r"(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


@dataclass(frozen=True, slots=True)
class SemanticVersion:
    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()
    build: tuple[str, ...] = ()


def parse_semver(version: str) -> SemanticVersion:
    resolved = str(version or "").strip()
    match = SEMVER_RE.match(resolved)
    if not match:
        raise ValueError(f"无效的版本号: {version}")

    prerelease = _split_identifiers(match.group("prerelease"))
    for identifier in prerelease:
        if identifier.isdigit() and len(identifier) > 1 and identifier.startswith("0"):
            raise ValueError(f"无效的版本号: {version}")

    build = _split_identifiers(match.group("build"))
    return SemanticVersion(
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        prerelease=prerelease,
        build=build,
    )


def is_valid_semver(version: str) -> bool:
    try:
        parse_semver(version)
    except ValueError:
        return False
    return True


def compare_semver(left: str, right: str) -> int:
    left_version = parse_semver(left)
    right_version = parse_semver(right)

    left_base = (left_version.major, left_version.minor, left_version.patch)
    right_base = (right_version.major, right_version.minor, right_version.patch)
    if left_base < right_base:
        return -1
    if left_base > right_base:
        return 1

    if not left_version.prerelease and not right_version.prerelease:
        return 0
    if not left_version.prerelease:
        return 1
    if not right_version.prerelease:
        return -1

    for left_identifier, right_identifier in zip(left_version.prerelease, right_version.prerelease):
        if left_identifier == right_identifier:
            continue

        left_numeric = left_identifier.isdigit()
        right_numeric = right_identifier.isdigit()
        if left_numeric and right_numeric:
            left_number = int(left_identifier)
            right_number = int(right_identifier)
            if left_number < right_number:
                return -1
            if left_number > right_number:
                return 1
            continue
        if left_numeric != right_numeric:
            return -1 if left_numeric else 1
        if left_identifier < right_identifier:
            return -1
        return 1

    if len(left_version.prerelease) < len(right_version.prerelease):
        return -1
    if len(left_version.prerelease) > len(right_version.prerelease):
        return 1
    return 0


def _split_identifiers(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part for part in value.split(".") if part)
