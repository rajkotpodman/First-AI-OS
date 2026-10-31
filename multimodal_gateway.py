#!/usr/bin/env python3
"""
multimodal_gateway.py - Root wrapper for AI OS Multimodal Input Gateway
"""
import os
import sys

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from multimodal_gateway import (
    VisionAnalysisResult,
    VoiceTranscriptionResult,
    MultimodalGateway,
    main
)

if __name__ == "__main__":
    main()
