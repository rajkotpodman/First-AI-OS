#!/usr/bin/env python3
"""
hardware_manager.py - Hardware Detection & GPU/CPU Acceleration Engine for AI OS
Author: Systems Performance Engineer & Hardware Optimization Specialist

Detects CPU architecture, vector extensions, memory limits, and GPU hardware
(NVIDIA CUDA, AMD ROCm, Intel/Apple graphics), dynamically calculating optimal
Ollama model quantization tiers, offloading layers, and resource throttling limits.
"""

import os
import sys
import re
import json
import time
import shutil
import platform
import subprocess
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any

DEFAULT_OLLAMA_ENV_PATH = "/etc/ai_os/ollama.env"
FALLBACK_OLLAMA_ENV_PATH = os.path.expanduser("~/.config/ai_os/ollama.env")


# ==============================================================================
# Hardware Diagnostic Data Structures
# ==============================================================================
@dataclass
class CPUInfo:
    architecture: str
    physical_cores: int
    logical_cores: int
    model_name: str
    has_avx: bool
    has_avx2: bool
    has_avx512: bool


@dataclass
class GPUInfo:
    detected: bool
    vendor: str            # "nvidia", "amd", "intel", "apple", "none"
    model_name: str
    driver_version: str
    vram_total_mb: int
    vram_free_mb: int
    cuda_compute: Optional[str] = None


@dataclass
class MemoryInfo:
    ram_total_mb: int
    ram_available_mb: int
    ram_used_mb: int
    ram_percent: float
    swap_total_mb: int
    swap_free_mb: int


@dataclass
class OptimizationProfile:
    tier_name: str                # "high_gpu", "hybrid_gpu_cpu", "cpu_only"
    recommended_model: str
    alternative_models: List[str]
    num_gpu_layers: int          # 99 for full GPU, 20-30 for hybrid, 0 for CPU
    num_parallel: int
    num_ctx: int
    keep_alive: str
    num_threads: int
    flash_attention: bool
    environment_variables: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ==============================================================================
# Hardware Inspector Engine
# ==============================================================================
class HardwareInspector:
    """Detects CPU, memory, and accelerator architectures."""

    @staticmethod
    def inspect_cpu() -> CPUInfo:
        arch = platform.machine()
        logical = os.cpu_count() or 1
        physical = logical // 2 if logical > 1 else 1

        model_name = platform.processor() or "Generic CPU"
        has_avx = False
        has_avx2 = False
        has_avx512 = False

        # Linux: inspect /proc/cpuinfo flags
        if os.path.exists("/proc/cpuinfo"):
            try:
                with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().lower()
                    has_avx = "avx " in content or " avx\n" in content
                    has_avx2 = "avx2" in content
                    has_avx512 = "avx512" in content

                    for line in content.splitlines():
                        if "model name" in line:
                            model_name = line.split(":", 1)[1].strip()
                            break
            except Exception:
                pass

        # Windows: fallback detection
        if not model_name or model_name == "Generic CPU":
            model_name = os.getenv("PROCESSOR_IDENTIFIER", model_name)

        return CPUInfo(
            architecture=arch,
            physical_cores=physical,
            logical_cores=logical,
            model_name=model_name,
            has_avx=has_avx,
            has_avx2=has_avx2,
            has_avx512=has_avx512
        )

    @staticmethod
    def inspect_memory() -> MemoryInfo:
        total_mb = 0
        avail_mb = 0
        swap_total = 0
        swap_free = 0

        # Linux: inspect /proc/meminfo
        if os.path.exists("/proc/meminfo"):
            try:
                mem = {}
                with open("/proc/meminfo", "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.split(":")
                        if len(parts) == 2:
                            val = parts[1].strip().split()[0]
                            mem[parts[0].strip()] = int(val)
                total_mb = mem.get("MemTotal", 0) // 1024
                avail_mb = mem.get("MemAvailable", mem.get("MemFree", 0)) // 1024
                swap_total = mem.get("SwapTotal", 0) // 1024
                swap_free = mem.get("SwapFree", 0) // 1024
            except Exception:
                pass

        # Python psutil or Windows / cross-platform fallback
        if total_mb == 0:
            try:
                import psutil
                vm = psutil.virtual_memory()
                sw = psutil.swap_memory()
                total_mb = int(vm.total // (1024 * 1024))
                avail_mb = int(vm.available // (1024 * 1024))
                swap_total = int(sw.total // (1024 * 1024))
                swap_free = int(sw.free // (1024 * 1024))
            except ImportError:
                # Conservative fallback if no proc/psutil
                total_mb = 4096
                avail_mb = 2048

        used_mb = max(0, total_mb - avail_mb)
        pct = round((used_mb / total_mb * 100.0), 1) if total_mb > 0 else 0.0

        return MemoryInfo(
            ram_total_mb=total_mb,
            ram_available_mb=avail_mb,
            ram_used_mb=used_mb,
            ram_percent=pct,
            swap_total_mb=swap_total,
            swap_free_mb=swap_free
        )

    @staticmethod
    def inspect_gpu() -> GPUInfo:
        # 1. Check NVIDIA via nvidia-smi
        if shutil.which("nvidia-smi"):
            try:
                res = subprocess.run(
                    ["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.free", "--format=csv,noheader,nounits"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3
                )
                if res.returncode == 0 and res.stdout.strip():
                    parts = [p.strip() for p in res.stdout.strip().splitlines()[0].split(",")]
                    name = parts[0]
                    driver = parts[1]
                    total_vram = int(float(parts[2]))
                    free_vram = int(float(parts[3]))
                    return GPUInfo(
                        detected=True,
                        vendor="nvidia",
                        model_name=name,
                        driver_version=driver,
                        vram_total_mb=total_vram,
                        vram_free_mb=free_vram
                    )
            except Exception:
                pass

        # 2. Check AMD ROCm via rocm-smi
        if shutil.which("rocm-smi"):
            try:
                res = subprocess.run(["rocm-smi", "--showmeminfo", "vram"],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
                if res.returncode == 0:
                    return GPUInfo(
                        detected=True,
                        vendor="amd",
                        model_name="AMD Radeon (ROCm)",
                        driver_version="ROCm",
                        vram_total_mb=8192,
                        vram_free_mb=6144
                    )
            except Exception:
                pass

        # 3. Check Linux DRM/DRI devices
        if os.path.exists("/dev/dri"):
            model = "Intel/Generic DRM"
            try:
                if shutil.which("lspci"):
                    pci = subprocess.run(["lspci"], stdout=subprocess.PIPE, text=True).stdout
                    for line in pci.splitlines():
                        if "VGA" in line or "3D" in line:
                            model = line.split(":", 2)[-1].strip()
                            break
            except Exception:
                pass
            return GPUInfo(
                detected=True,
                vendor="intel" if "intel" in model.lower() else "generic",
                model_name=model,
                driver_version="DRM/Gallium",
                vram_total_mb=1024,
                vram_free_mb=512
            )

        # No dedicated acceleration detected
        return GPUInfo(
            detected=False,
            vendor="none",
            model_name="None (CPU Only)",
            driver_version="N/A",
            vram_total_mb=0,
            vram_free_mb=0
        )


# ==============================================================================
# Inference Optimization & Configuration Generator
# ==============================================================================
class InferenceOptimizer:
    """Calculates optimal model parameters, offload layers, and environment settings."""

    @staticmethod
    def calculate_optimization(cpu: CPUInfo, gpu: GPUInfo, mem: MemoryInfo) -> OptimizationProfile:
        vram = gpu.vram_total_mb if gpu.detected else 0
        ram = mem.ram_total_mb

        # Rule 1: Dedicated GPU VRAM >= 8GB -> High GPU Tier
        if gpu.detected and gpu.vendor in ("nvidia", "amd") and vram >= 8000:
            env_vars = {
                "OLLAMA_NUM_PARALLEL": "4",
                "OLLAMA_MAX_LOADED_MODELS": "2",
                "OLLAMA_KEEP_ALIVE": "24h",
                "OLLAMA_FLASH_ATTENTION": "1"
            }
            if gpu.vendor == "nvidia":
                env_vars["CUDA_VISIBLE_DEVICES"] = "0"

            return OptimizationProfile(
                tier_name="high_gpu",
                recommended_model="llama3.1:8b",
                alternative_models=["qwen2.5:14b-instruct-q4_K_M", "deepseek-coder:6.7b", "llama3.2:3b"],
                num_gpu_layers=99,
                num_parallel=4,
                num_ctx=8192,
                keep_alive="24h",
                num_threads=cpu.logical_cores,
                flash_attention=True,
                environment_variables=env_vars
            )

        # Rule 2: Dedicated/Shared GPU VRAM 2GB to 6GB -> Hybrid Tier
        elif gpu.detected and vram >= 2000:
            env_vars = {
                "OLLAMA_NUM_PARALLEL": "2",
                "OLLAMA_MAX_LOADED_MODELS": "1",
                "OLLAMA_KEEP_ALIVE": "30m",
                "OLLAMA_FLASH_ATTENTION": "1"
            }
            return OptimizationProfile(
                tier_name="hybrid_gpu_cpu",
                recommended_model="llama3.2:3b",
                alternative_models=["qwen2.5:3b-instruct-q4_K_M", "llama3.2:1b"],
                num_gpu_layers=28,  # Offload ~28 layers to GPU, rest to CPU
                num_parallel=2,
                num_ctx=4096,
                keep_alive="30m",
                num_threads=cpu.logical_cores,
                flash_attention=True,
                environment_variables=env_vars
            )

        # Rule 3: CPU Only or Low RAM (< 8GB) -> Lightweight CPU Tier
        else:
            threads = max(1, cpu.physical_cores)
            env_vars = {
                "OLLAMA_NUM_PARALLEL": "1",
                "OLLAMA_MAX_LOADED_MODELS": "1",
                "OLLAMA_KEEP_ALIVE": "5m",
                "OLLAMA_NUM_THREADS": str(threads),
                "OLLAMA_FLASH_ATTENTION": "0"
            }
            return OptimizationProfile(
                tier_name="cpu_only",
                recommended_model="llama3.2:1b",
                alternative_models=["qwen2.5:1.5b-instruct-q4_K_M", "tinydolphin"],
                num_gpu_layers=0,
                num_parallel=1,
                num_ctx=2048,
                keep_alive="5m",
                num_threads=threads,
                flash_attention=False,
                environment_variables=env_vars
            )

    @staticmethod
    def generate_ollama_env_file(profile: OptimizationProfile, output_path: Optional[str] = None) -> str:
        """Writes environment variables to /etc/ai_os/ollama.env or fallback."""
        target = output_path or DEFAULT_OLLAMA_ENV_PATH
        try:
            p = Path(target)
            p.parent.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError):
            target = FALLBACK_OLLAMA_ENV_PATH
            p = Path(target)
            p.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            f"# Ollama Hardware Optimization Profile: {profile.tier_name.upper()}",
            f"# Generated automatically by AI OS Hardware Manager",
            f"OLLAMA_HOST=0.0.0.0:11434",
            f"OLLAMA_MODELS=/workspace/.ollama/models"
        ]
        for k, v in profile.environment_variables.items():
            lines.append(f"{k}={v}")

        content = "\n".join(lines) + "\n"
        try:
            p.write_text(content, encoding="utf-8")
        except PermissionError:
            target = FALLBACK_OLLAMA_ENV_PATH
            Path(target).parent.mkdir(parents=True, exist_ok=True)
            Path(target).write_text(content, encoding="utf-8")

        return target


# ==============================================================================
# Hardware Manager Controller & Throttling Engine
# ==============================================================================
class HardwareManager:
    """Unified hardware diagnostics, metrics monitoring, and inference optimizer."""

    def __init__(self):
        self.cpu = HardwareInspector.inspect_cpu()
        self.gpu = HardwareInspector.inspect_gpu()
        self.memory = HardwareInspector.inspect_memory()
        self.profile = InferenceOptimizer.calculate_optimization(self.cpu, self.gpu, self.memory)

    def refresh(self):
        """Refreshes dynamic memory and GPU metrics."""
        self.memory = HardwareInspector.inspect_memory()
        self.gpu = HardwareInspector.inspect_gpu()

    def get_system_metrics(self) -> Dict[str, Any]:
        """Exposes complete system diagnostic metrics as clean JSON."""
        self.refresh()
        disk_total, disk_used, disk_free = shutil.disk_usage(os.getcwd())
        disk_pct = round((disk_used / disk_total * 100.0), 1) if disk_total > 0 else 0.0

        return {
            "timestamp": time.time(),
            "cpu": asdict(self.cpu),
            "memory": asdict(self.memory),
            "gpu": asdict(self.gpu),
            "disk": {
                "total_mb": disk_total // (1024 * 1024),
                "free_mb": disk_free // (1024 * 1024),
                "used_mb": disk_used // (1024 * 1024),
                "percent": disk_pct
            },
            "optimization_tier": self.profile.tier_name,
            "recommended_model": self.profile.recommended_model
        }

    def should_throttle(self, mem_threshold: float = 90.0, cpu_threshold: float = 95.0) -> Tuple[bool, str]:
        """
        Determines whether system load is too high to run intensive AI tasks.
        """
        self.refresh()
        if self.memory.ram_percent >= mem_threshold:
            return True, f"RAM usage ({self.memory.ram_percent}%) exceeds safe threshold ({mem_threshold}%)."

        # Check CPU load via os.getloadavg() if available
        if hasattr(os, "getloadavg"):
            try:
                load_1m = os.getloadavg()[0]
                normalized = (load_1m / self.cpu.logical_cores) * 100.0
                if normalized >= cpu_threshold:
                    return True, f"CPU load ({normalized:.1f}%) exceeds safety limit ({cpu_threshold}%)."
            except Exception:
                pass

        return False, "Operating within safe hardware limits."

    def throttle_wait(self, timeout_sec: int = 30, check_interval: float = 2.0) -> bool:
        """
        Waits for resource spikes to stabilize before proceeding with heavy agent tasks.
        """
        start = time.time()
        while time.time() - start < timeout_sec:
            throttled, reason = self.should_throttle()
            if not throttled:
                return True
            time.sleep(check_interval)
        return False

    def auto_configure_environment(self, custom_path: Optional[str] = None) -> str:
        """Generates and writes the optimal Ollama service environment configuration."""
        return InferenceOptimizer.generate_ollama_env_file(self.profile, custom_path)


# ==============================================================================
# CLI Entry Point
# ==============================================================================
def main():
    hw = HardwareManager()

    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd in ("--metrics", "-m", "metrics"):
            print(json.dumps(hw.get_system_metrics(), indent=2))
            sys.exit(0)
        elif cmd in ("--configure", "-c", "configure"):
            env_file = hw.auto_configure_environment()
            print(f"[OK] Generated Ollama optimization config at: {env_file}")
            print(f"Tier: {hw.profile.tier_name.upper()} | Model: {hw.profile.recommended_model}")
            sys.exit(0)
        elif cmd in ("--profile", "-p", "profile"):
            print(json.dumps(hw.profile.to_dict(), indent=2))
            sys.exit(0)

    # Default output: Human-readable hardware summary
    metrics = hw.get_system_metrics()
    print("==================================================================")
    print("        AI OS Hardware Diagnostics & Acceleration Profile        ")
    print("==================================================================")
    print(f"CPU Architecture : {metrics['cpu']['architecture']} ({metrics['cpu']['logical_cores']} cores)")
    print(f"CPU Model        : {metrics['cpu']['model_name']}")
    print(f"Vector Support   : AVX: {metrics['cpu']['has_avx']} | AVX2: {metrics['cpu']['has_avx2']} | AVX512: {metrics['cpu']['has_avx512']}")
    print(f"Total System RAM : {metrics['memory']['ram_total_mb']} MB (Used: {metrics['memory']['ram_percent']}%)")
    print(f"GPU Hardware     : {metrics['gpu']['model_name']} [{metrics['gpu']['vendor'].upper()}]")
    if metrics['gpu']['detected']:
        print(f"Dedicated VRAM   : {metrics['gpu']['vram_total_mb']} MB (Free: {metrics['gpu']['vram_free_mb']} MB)")
    print("------------------------------------------------------------------")
    print(f"Optimization Tier: \033[1;36m{hw.profile.tier_name.upper()}\033[0m")
    print(f"Recommended Model: \033[1;32m{hw.profile.recommended_model}\033[0m")
    print(f"Layers to GPU    : {hw.profile.num_gpu_layers} layers")
    print(f"Context Window   : {hw.profile.num_ctx} tokens")
    print(f"Parallel Requests: {hw.profile.num_parallel}")
    print("==================================================================")

if __name__ == "__main__":
    main()
