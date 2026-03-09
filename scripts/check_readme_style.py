#!/usr/bin/env python3

from pathlib import Path

MODULE_REQUIRED = [
    "## Description",
    "## Usage",
    "## Arguments",
    "## Input",
    "## Output",
    "## Install",
]

ROOT_REQUIRED = [
    "## Overview",
    "## Supported Formats",
    "## Pipeline Modules",
    "## Configuration",
    "## Build",
    "## Usage",
]


def section_positions(readme_path: Path) -> dict[str, int]:
    lines = readme_path.read_text(encoding="utf-8").splitlines()
    return {
        line.strip(): index
        for index, line in enumerate(lines)
        if line.startswith("## ")
    }


def main() -> None:
    errors: list[str] = []

    for readme in sorted(Path(".").glob("*/README.md")):
        if readme.parts[0] in {"submodules", "ontology-management-base"}:
            continue
        positions = section_positions(readme)
        missing = [section for section in MODULE_REQUIRED if section not in positions]
        if missing:
            errors.append(f"{readme}: missing sections: {', '.join(missing)}")
            continue

        order = [positions[section] for section in MODULE_REQUIRED]
        if order != sorted(order):
            errors.append(f"{readme}: sections are out of order")

    root = Path("README.md")
    root_positions = section_positions(root)
    missing = [section for section in ROOT_REQUIRED if section not in root_positions]
    if missing:
        errors.append(f"README.md: missing sections: {', '.join(missing)}")

    if errors:
        print("README check failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("README structure checks passed.")


if __name__ == "__main__":
    main()
