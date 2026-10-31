#!/usr/bin/env python3
"""
ai_terminal_ui.py - Root wrapper for AI OS Terminal UI framework
"""
import os
import sys

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from ai_terminal_ui import (
    AITerminalUI,
    AIStreamStdoutWrapper,
    CUSTOM_THEME,
    main
)

if __name__ == "__main__":
    main()
