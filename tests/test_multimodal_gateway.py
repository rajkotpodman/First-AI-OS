#!/usr/bin/env python3
"""
test_multimodal_gateway.py - Unit tests for Multimodal Input Gateway (Voice & Image Listener)
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from multimodal_gateway import (
    MultimodalGateway,
    VisionAnalysisResult,
    VoiceTranscriptionResult
)


class TestMultimodalGateway(unittest.TestCase):
    """Test audio capture, whisper transcription, vision parsing, and TTS."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.gateway = MultimodalGateway()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_audio_capture_and_dummy_wav(self):
        wav_path = os.path.join(self.tmp_dir.name, "test_audio.wav")
        ok, res_path = self.gateway.capture_audio(duration_seconds=1, output_wav=wav_path)
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(res_path))
        self.assertGreater(os.path.getsize(res_path), 0)

    def test_transcribe_audio(self):
        wav_path = os.path.join(self.tmp_dir.name, "test_speech.wav")
        self.gateway._create_dummy_wav(wav_path)
        res = self.gateway.transcribe_audio(wav_path)
        self.assertIsInstance(res, VoiceTranscriptionResult)
        self.assertTrue(len(res.transcript) > 0)
        self.assertEqual(res.audio_path, wav_path)

    def test_screenshot_and_dummy_png(self):
        png_path = os.path.join(self.tmp_dir.name, "screen.png")
        ok, res_path = self.gateway.capture_screenshot(output_path=png_path)
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(res_path))
        self.assertGreater(os.path.getsize(res_path), 0)

    def test_encode_image_base64(self):
        png_path = os.path.join(self.tmp_dir.name, "sample.png")
        self.gateway._create_dummy_png(png_path)
        b64 = self.gateway.encode_image_base64(png_path)
        self.assertIsInstance(b64, str)
        self.assertTrue(len(b64) > 10)

    def test_analyze_image(self):
        png_path = os.path.join(self.tmp_dir.name, "error_screenshot.png")
        self.gateway._create_dummy_png(png_path)
        analysis = self.gateway.analyze_image(png_path, user_prompt="Diagnose this error")
        self.assertIsInstance(analysis, VisionAnalysisResult)
        self.assertEqual(analysis.image_path, png_path)
        self.assertTrue(len(analysis.description) > 0)
        # Verify JSON serialization works
        json_str = analysis.to_json()
        self.assertIn("image_path", json_str)

    def test_tts_speak_interface(self):
        # speak() should handle text cleanly without unhandled exceptions
        try:
            self.gateway.speak("AI OS multimodal speech test")
        except Exception as e:
            self.fail(f"gateway.speak raised unexpected exception: {e}")


if __name__ == "__main__":
    unittest.main()
