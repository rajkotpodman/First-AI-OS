#!/usr/bin/env python3
"""
test_hardware_manager.py - Unit tests for Hardware Detection & Acceleration Engine
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from hardware_manager import (
    CPUInfo,
    GPUInfo,
    MemoryInfo,
    InferenceOptimizer,
    HardwareInspector,
    HardwareManager
)

class TestInferenceOptimizerTiers(unittest.TestCase):
    """Test optimization tier calculation across GPU and memory variations."""

    def setUp(self):
        self.dummy_cpu = CPUInfo(
            architecture="x86_64",
            physical_cores=8,
            logical_cores=16,
            model_name="Intel Core i9",
            has_avx=True,
            has_avx2=True,
            has_avx512=False
        )

    def test_tier1_high_gpu_acceleration(self):
        gpu = GPUInfo(
            detected=True,
            vendor="nvidia",
            model_name="NVIDIA GeForce RTX 4090",
            driver_version="535.129",
            vram_total_mb=24576,
            vram_free_mb=22000
        )
        mem = MemoryInfo(
            ram_total_mb=32768,
            ram_available_mb=24000,
            ram_used_mb=8768,
            ram_percent=26.7,
            swap_total_mb=8192,
            swap_free_mb=8192
        )

        profile = InferenceOptimizer.calculate_optimization(self.dummy_cpu, gpu, mem)
        self.assertEqual(profile.tier_name, "high_gpu")
        self.assertEqual(profile.recommended_model, "llama3.1:8b")
        self.assertEqual(profile.num_gpu_layers, 99)
        self.assertEqual(profile.num_parallel, 4)
        self.assertTrue(profile.flash_attention)
        self.assertIn("CUDA_VISIBLE_DEVICES", profile.environment_variables)

    def test_tier2_hybrid_gpu_cpu_offload(self):
        gpu = GPUInfo(
            detected=True,
            vendor="nvidia",
            model_name="NVIDIA GeForce GTX 1650",
            driver_version="535.129",
            vram_total_mb=4096,
            vram_free_mb=3500
        )
        mem = MemoryInfo(
            ram_total_mb=16384,
            ram_available_mb=10000,
            ram_used_mb=6384,
            ram_percent=38.9,
            swap_total_mb=4096,
            swap_free_mb=4096
        )

        profile = InferenceOptimizer.calculate_optimization(self.dummy_cpu, gpu, mem)
        self.assertEqual(profile.tier_name, "hybrid_gpu_cpu")
        self.assertEqual(profile.recommended_model, "llama3.2:3b")
        self.assertEqual(profile.num_gpu_layers, 28)
        self.assertEqual(profile.num_parallel, 2)
        self.assertEqual(profile.num_ctx, 4096)

    def test_tier3_cpu_only_low_resource(self):
        gpu = GPUInfo(
            detected=False,
            vendor="none",
            model_name="None",
            driver_version="N/A",
            vram_total_mb=0,
            vram_free_mb=0
        )
        mem = MemoryInfo(
            ram_total_mb=4096,
            ram_available_mb=1500,
            ram_used_mb=2596,
            ram_percent=63.4,
            swap_total_mb=2048,
            swap_free_mb=2048
        )

        profile = InferenceOptimizer.calculate_optimization(self.dummy_cpu, gpu, mem)
        self.assertEqual(profile.tier_name, "cpu_only")
        self.assertEqual(profile.recommended_model, "llama3.2:1b")
        self.assertEqual(profile.num_gpu_layers, 0)
        self.assertEqual(profile.num_parallel, 1)
        self.assertEqual(profile.num_ctx, 2048)
        self.assertEqual(profile.keep_alive, "5m")

class TestHardwareManagerMetricsAndConfig(unittest.TestCase):
    """Test environment generation and throttling detection."""

    def test_generate_ollama_env(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            env_file = tmp.name

        try:
            mgr = HardwareManager()
            generated_path = mgr.auto_configure_environment(custom_path=env_file)
            content = Path(generated_path).read_text(encoding="utf-8")

            self.assertIn("OLLAMA_HOST=0.0.0.0:11434", content)
            self.assertIn("OLLAMA_MODELS=/workspace/.ollama/models", content)
            self.assertIn("OLLAMA_NUM_PARALLEL=", content)
        finally:
            if os.path.exists(env_file):
                os.remove(env_file)

    def test_throttling_check(self):
        mgr = HardwareManager()
        # Force low threshold to test throttling response
        throttled, reason = mgr.should_throttle(mem_threshold=1.0)
        self.assertTrue(throttled)
        self.assertIn("exceeds safe threshold", reason)

        # High threshold should not throttle
        throttled, reason = mgr.should_throttle(mem_threshold=100.0, cpu_threshold=100.0)
        self.assertFalse(throttled)

if __name__ == "__main__":
    unittest.main()
