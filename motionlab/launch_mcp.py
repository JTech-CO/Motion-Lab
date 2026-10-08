"""Absolute-script MCP entry point for clients without a cwd setting."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from motionlab.__main__ import main  # noqa: E402


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] + ["mcp"]))
