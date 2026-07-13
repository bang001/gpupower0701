#!/usr/bin/env python3
"""Compatibility entry point for the platform-generic L2 selector."""

import sys

from select_l2_path_configuration import main


if __name__ == "__main__":
    compatibility_defaults = {
        "--target-profile": "a100",
        "--out-csv": "results/summary/a100_l2_path_selection.csv",
        "--out-md": "results/summary/a100_l2_path_selection.md",
        "--out-env": "results/summary/a100_l2_path_selection.env",
    }
    for option, value in compatibility_defaults.items():
        if not any(
            arg == option or arg.startswith(f"{option}=") for arg in sys.argv[1:]
        ):
            sys.argv.extend([option, value])
    raise SystemExit(main())
