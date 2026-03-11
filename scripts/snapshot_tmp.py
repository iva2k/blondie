#!/usr/bin/env python3

"""Make a snapshot - copy/move the _tmp directory to a dated _tmp.YYYY-MMDD-hhmm directory."""

import argparse
import os
import shutil
import sys
from datetime import datetime


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Snapshot directory.")
    parser.add_argument("src", nargs="?", default="_tmp", help="Source directory (default: _tmp)")
    parser.add_argument("dst", nargs="?", help="Destination directory (optional)")
    parser.add_argument("--move", action="store_true", help="Move instead of copy")
    return parser.parse_args()


def main():
    """CLI."""
    args = parse_args()
    src = args.src
    if not os.path.exists(src):
        print(f"Error: Source directory {src} does not exist.")
        return 1

    if args.dst:
        dst = args.dst
    else:
        # Format: src.YYYY-MMDD-hhmm
        timestamp = datetime.now().strftime("%Y-%m%d-%H%M")
        src_stripped = src.rstrip("/\\")
        dst = f"{src_stripped}.{timestamp}"

    if os.path.exists(dst):
        print(f"Error: Destination directory {dst} already exists.")
        return 1

    try:
        if args.move:
            print(f"Moving {src} to {dst}...")
            shutil.move(src, dst)
        else:
            print(f"Copying {src} to {dst}...")
            shutil.copytree(src, dst)

        print(f"Snapshot saved to {dst}")
    # pylint: disable-next=broad-exception-caught
    except Exception as e:
        print(f"Error: Failed to snapshot {src} to {dst}. {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
