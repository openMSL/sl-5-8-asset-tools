#!/usr/bin/env python3

import py_compile
import subprocess


def main() -> None:
    files = subprocess.check_output(["git", "ls-files", "*.py"], text=True).splitlines()
    for file_path in files:
        py_compile.compile(file_path, doraise=True)
    print(f"Compiled {len(files)} Python files successfully.")


if __name__ == "__main__":
    main()
