#!/usr/bin/env python3
"""
personal_memory.py - Root wrapper for AI OS Long-Term Personal Memory Engine
"""
import os
import sys

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from personal_memory import (
    SimpleEmbeddingEngine,
    MemoryRecord,
    PersonalMemoryEngine,
    main
)

if __name__ == "__main__":
    main()
