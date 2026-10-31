#!/usr/bin/env python3
"""
model_router.py - Hybrid Offline/Online AI Router & Network Fallback Subsystem
Author: Distributed Systems Engineer & API Gateway Specialist

Manages dynamic routing between local Ollama LLMs and cloud AI APIs (Anthropic,
OpenAI, Google Gemini) based on network reachability, task complexity, and
privacy sensitivity with automated zero-downtime local failover.
"""

import os
import sys
import re
import json
import time
import socket
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any

# HTTP request handler with requests and urllib fallback
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    from ai_shell_agent import ConfigManager
except ImportError:
    ConfigManager = None


# ==============================================================================
# Unified Data Models
# ==============================================================================
@dataclass
class ModelRequest:
    prompt: str
    system_context: str = ""
    temperature: float = 0.2
    max_tokens: int = 4096
    force_local: bool = False
    task_complexity: Optional[str] = None  # "simple", "complex", "privacy_sensitive"


@dataclass
class ModelResponse:
    content: str
    provider: str            # "ollama", "anthropic", "openai", "gemini"
    model: str
    latency_ms: float
    network_status: str      # "ONLINE", "OFFLINE"
    fallback_triggered: bool = False
    fallback_reason: Optional[str] = None
    tokens_used: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# ==============================================================================
# Network Connectivity Monitor
# ==============================================================================
class NetworkMonitor:
    """Probes internet reachability with dynamic TTL caching and manual override."""

    PROBE_TARGETS = [
        ("1.1.1.1", 53),
        ("8.8.8.8", 53),
        ("9.9.9.9", 53)
    ]

    def __init__(self, cache_ttl_seconds: float = 20.0):
        self.cache_ttl = cache_ttl_seconds
        self._last_check_time: float = 0.0
        self._cached_status: str = "OFFLINE"
        self._forced_mode: Optional[str] = None  # "auto", "online", "offline"

    def set_forced_mode(self, mode: Optional[str]):
        """Forces the monitor state for debugging or user preference."""
        if mode in ("online", "offline", "auto", None):
            self._forced_mode = None if mode == "auto" else mode.upper() if mode else None

    def get_status(self) -> str:
        """Returns 'ONLINE' or 'OFFLINE'."""
        if self._forced_mode:
            return self._forced_mode

        now = time.time()
        if now - self._last_check_time < self.cache_ttl:
            return self._cached_status

        self._cached_status = "ONLINE" if self._probe_internet() else "OFFLINE"
        self._last_check_time = now
        return self._cached_status

    def is_online(self) -> bool:
        return self.get_status() == "ONLINE"

    def _probe_internet(self) -> bool:
        """Fast TCP socket probe to any major public DNS resolver."""
        for host, port in self.PROBE_TARGETS:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1.2)
                s.connect((host, port))
                s.close()
                return True
            except (socket.timeout, OSError):
                continue
        return False


# ==============================================================================
# Task Complexity & Privacy Classifier
# ==============================================================================
class TaskClassifier:
    """Classifies prompts to determine if cloud offloading is justified and safe."""

    PRIVACY_KEYWORDS = {
        "password", "secret", "private key", "api_key", "token", "credential",
        "shadow", "sudoers", "ssh_key", "id_rsa", "env", "dotenv", "auth_token",
        "bearer", "credit_card", "ssn", "confidential"
    }

    COMPLEXITY_KEYWORDS = {
        "architect", "full-stack", "refactor entire", "system design",
        "multi-step reasoning", "optimize kernel", "build complete project",
        "distributed system", "ast parser", "concurrency model", "compiler"
    }

    @classmethod
    def classify(cls, prompt: str, system_context: str = "") -> str:
        combined = f"{prompt}\n{system_context}".lower()

        # 1. Strict Privacy Check -> Always local
        for kw in cls.PRIVACY_KEYWORDS:
            if re.search(r"\b" + re.escape(kw) + r"\b", combined):
                return "privacy_sensitive"

        # 2. Check explicitly high complexity keywords
        for kw in cls.COMPLEXITY_KEYWORDS:
            if re.search(r"\b" + re.escape(kw) + r"\b", combined):
                return "complex"

        # 3. Prompt length heuristic: extensive detailed requests -> complex
        if len(prompt.split()) > 120 or prompt.count("\n") > 10:
            return "complex"

        return "simple"


# ==============================================================================
# Provider Adapter Interfaces
# ==============================================================================
class BaseAIProvider(ABC):
    """Abstract base provider for inference engines."""

    @abstractmethod
    def get_provider_name(self) -> str:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def execute_request(self, req: ModelRequest) -> Tuple[bool, str, Dict[str, Any]]:
        """Returns: (success, response_content_or_error, metadata)"""
        pass


class OllamaProvider(BaseAIProvider):
    """Local offline inference provider connecting to Ollama at localhost:11434."""

    def __init__(self,
                 endpoint: str = "http://127.0.0.1:11434",
                 default_model: str = "llama3.2:3b",
                 timeout_seconds: int = 60):
        self.endpoint = endpoint.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout_seconds

    def get_provider_name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        url = f"{self.endpoint}/api/tags"
        try:
            if HAS_REQUESTS:
                res = requests.get(url, timeout=1.5)
                return res.status_code == 200
            else:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    return resp.status == 200
        except Exception:
            return False

    def execute_request(self, req: ModelRequest) -> Tuple[bool, str, Dict[str, Any]]:
        url = f"{self.endpoint}/api/chat"
        messages = []
        if req.system_context:
            messages.append({"role": "system", "content": req.system_context})
        messages.append({"role": "user", "content": req.prompt})

        payload = {
            "model": self.default_model,
            "messages": messages,
            "options": {
                "temperature": req.temperature,
                "num_ctx": req.max_tokens
            },
            "stream": False
        }

        try:
            if HAS_REQUESTS:
                res = requests.post(url, json=payload, timeout=self.timeout)
                if res.status_code == 200:
                    data = res.json()
                    content = data.get("message", {}).get("content", "")
                    tokens = data.get("eval_count", 0)
                    return True, content, {"model": self.default_model, "tokens": tokens}
                return False, f"Ollama HTTP {res.status_code}: {res.text}", {}
            else:
                data_bytes = json.dumps(payload).encode("utf-8")
                http_req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(http_req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    content = data.get("message", {}).get("content", "")
                    return True, content, {"model": self.default_model, "tokens": data.get("eval_count", 0)}
        except Exception as e:
            return False, f"Ollama connection error: {e}", {}


class OpenAIProvider(BaseAIProvider):
    """Cloud provider for OpenAI or OpenAI-compatible inference endpoints."""

    def __init__(self,
                 api_key: Optional[str] = None,
                 endpoint: str = "https://api.openai.com/v1/chat/completions",
                 model: str = "gpt-4o-mini",
                 timeout_seconds: int = 35):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.endpoint = endpoint
        self.model = model
        self.timeout = timeout_seconds

    def get_provider_name(self) -> str:
        return "openai"

    def is_available(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def execute_request(self, req: ModelRequest) -> Tuple[bool, str, Dict[str, Any]]:
        if not self.is_available():
            return False, "OpenAI API key is missing or not configured.", {}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        messages = []
        if req.system_context:
            messages.append({"role": "system", "content": req.system_context})
        messages.append({"role": "user", "content": req.prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens
        }

        try:
            if HAS_REQUESTS:
                res = requests.post(self.endpoint, headers=headers, json=payload, timeout=self.timeout)
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"]
                    tokens = data.get("usage", {}).get("total_tokens", 0)
                    return True, content, {"model": self.model, "tokens": tokens}
                return False, f"OpenAI API HTTP {res.status_code}: {res.text[:300]}", {}
            else:
                data_bytes = json.dumps(payload).encode("utf-8")
                http_req = urllib.request.Request(self.endpoint, data=data_bytes, headers=headers)
                with urllib.request.urlopen(http_req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    content = data["choices"][0]["message"]["content"]
                    tokens = data.get("usage", {}).get("total_tokens", 0)
                    return True, content, {"model": self.model, "tokens": tokens}
        except Exception as e:
            return False, f"OpenAI API Exception: {e}", {}


class AnthropicProvider(BaseAIProvider):
    """Cloud provider for Anthropic Claude API."""

    def __init__(self,
                 api_key: Optional[str] = None,
                 model: str = "claude-3-5-sonnet-20241022",
                 timeout_seconds: int = 40):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.endpoint = "https://api.anthropic.com/v1/messages"
        self.model = model
        self.timeout = timeout_seconds

    def get_provider_name(self) -> str:
        return "anthropic"

    def is_available(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def execute_request(self, req: ModelRequest) -> Tuple[bool, str, Dict[str, Any]]:
        if not self.is_available():
            return False, "Anthropic API key is missing or not configured.", {}

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
            "messages": [{"role": "user", "content": req.prompt}]
        }
        if req.system_context:
            payload["system"] = req.system_context

        try:
            if HAS_REQUESTS:
                res = requests.post(self.endpoint, headers=headers, json=payload, timeout=self.timeout)
                if res.status_code == 200:
                    data = res.json()
                    text_parts = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
                    tokens = data.get("usage", {}).get("output_tokens", 0)
                    return True, "".join(text_parts), {"model": self.model, "tokens": tokens}
                return False, f"Anthropic HTTP {res.status_code}: {res.text[:300]}", {}
            else:
                data_bytes = json.dumps(payload).encode("utf-8")
                http_req = urllib.request.Request(self.endpoint, data=data_bytes, headers=headers)
                with urllib.request.urlopen(http_req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    text_parts = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
                    tokens = data.get("usage", {}).get("output_tokens", 0)
                    return True, "".join(text_parts), {"model": self.model, "tokens": tokens}
        except Exception as e:
            return False, f"Anthropic Exception: {e}", {}


class GeminiProvider(BaseAIProvider):
    """Cloud provider for Google Gemini API."""

    def __init__(self,
                 api_key: Optional[str] = None,
                 model: str = "gemini-1.5-flash",
                 timeout_seconds: int = 35):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model
        self.timeout = timeout_seconds

    def get_provider_name(self) -> str:
        return "gemini"

    def is_available(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def execute_request(self, req: ModelRequest) -> Tuple[bool, str, Dict[str, Any]]:
        if not self.is_available():
            return False, "Gemini API key is missing or not configured.", {}

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}

        parts = []
        if req.system_context:
            parts.append({"text": f"System Context:\n{req.system_context}\n\n"})
        parts.append({"text": req.prompt})

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": req.temperature,
                "maxOutputTokens": req.max_tokens
            }
        }

        try:
            if HAS_REQUESTS:
                res = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        return True, text, {"model": self.model, "tokens": 0}
                return False, f"Gemini HTTP {res.status_code}: {res.text[:300]}", {}
            else:
                data_bytes = json.dumps(payload).encode("utf-8")
                http_req = urllib.request.Request(url, data=data_bytes, headers=headers)
                with urllib.request.urlopen(http_req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    candidates = data.get("candidates", [])
                    if candidates:
                        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        return True, text, {"model": self.model, "tokens": 0}
        except Exception as e:
            return False, f"Gemini Exception: {e}", {}
        return False, "Unknown Gemini response format.", {}


# ==============================================================================
# Unified Intelligence Router Engine
# ==============================================================================
class ModelRouter:
    """
    Central API Gateway & Intelligence Router that orchestrates model selection,
    network checking, task-based cloud routing, and automatic local fallback.
    """

    def __init__(self,
                 config: Optional[Dict[str, Any]] = None,
                 network_monitor: Optional[NetworkMonitor] = None):
        self.config = config or (ConfigManager.load() if ConfigManager else {})
        self.network = network_monitor or NetworkMonitor()

        # Initialize providers
        local_cfg = self.config.get("ai_routing", {}).get("local", {})
        self.local_provider = OllamaProvider(
            endpoint=local_cfg.get("endpoint", "http://127.0.0.1:11434"),
            default_model=local_cfg.get("model", "llama3.2:3b"),
            timeout_seconds=local_cfg.get("timeout_seconds", 60)
        )

        remote_cfg = self.config.get("ai_routing", {}).get("remote", {})
        self.cloud_providers: List[BaseAIProvider] = [
            AnthropicProvider(),
            OpenAIProvider(
                endpoint=remote_cfg.get("endpoint", "https://api.openai.com/v1/chat/completions"),
                model=remote_cfg.get("model", "gpt-4o-mini")
            ),
            GeminiProvider()
        ]

    def select_active_cloud_provider(self) -> Optional[BaseAIProvider]:
        """Finds the first available cloud provider with valid API credentials."""
        for provider in self.cloud_providers:
            if provider.is_available():
                return provider
        return None

    def generate(self,
                 prompt: str,
                 system_context: str = "",
                 task_complexity: Optional[str] = None,
                 force_local: bool = False,
                 temperature: float = 0.2,
                 max_tokens: int = 4096) -> ModelResponse:
        """
        Unified inference entry point for the entire OS.
        Determines route, executes, and automatically falls back to local on error.
        """
        req = ModelRequest(
            prompt=prompt,
            system_context=system_context,
            temperature=temperature,
            max_tokens=max_tokens,
            force_local=force_local,
            task_complexity=task_complexity
        )

        net_status = self.network.get_status()
        start_time = time.time()

        # Determine complexity & sensitivity if not explicitly set
        complexity = req.task_complexity or TaskClassifier.classify(prompt, system_context)

        # ----------------------------------------------------------------------
        # Routing Decision Tree
        # ----------------------------------------------------------------------
        # Case 1: Force local OR Network OFFLINE OR Privacy Sensitive OR Simple Task
        if force_local or net_status == "OFFLINE" or complexity in ("simple", "privacy_sensitive"):
            return self._execute_local(req, net_status, start_time)

        # Case 2: Online with Complex Task -> Attempt Cloud Routing
        cloud_provider = self.select_active_cloud_provider()
        if not cloud_provider:
            # No cloud API keys available -> Route to local model
            return self._execute_local(req, net_status, start_time)

        # Execute Cloud Model
        cloud_success, cloud_res, meta = cloud_provider.execute_request(req)
        latency = (time.time() - start_time) * 1000.0

        if cloud_success:
            return ModelResponse(
                content=cloud_res,
                provider=cloud_provider.get_provider_name(),
                model=meta.get("model", "cloud"),
                latency_ms=round(latency, 2),
                network_status=net_status,
                fallback_triggered=False,
                tokens_used=meta.get("tokens", 0)
            )

        # ----------------------------------------------------------------------
        # Automated Failover: Cloud Failed -> Fallback to Local Ollama
        # ----------------------------------------------------------------------
        failover_reason = f"Cloud provider '{cloud_provider.get_provider_name()}' error: {cloud_res}"
        local_response = self._execute_local(req, net_status, start_time)
        local_response.fallback_triggered = True
        local_response.fallback_reason = failover_reason
        return local_response

    def _execute_local(self, req: ModelRequest, net_status: str, start_time: float) -> ModelResponse:
        """Directly executes request using local Ollama model."""
        ok, res, meta = self.local_provider.execute_request(req)
        latency = (time.time() - start_time) * 1000.0

        if ok:
            return ModelResponse(
                content=res,
                provider="ollama",
                model=meta.get("model", self.local_provider.default_model),
                latency_ms=round(latency, 2),
                network_status=net_status,
                fallback_triggered=False,
                tokens_used=meta.get("tokens", 0)
            )
        else:
            return ModelResponse(
                content=f"[Local AI Error] {res}",
                provider="ollama",
                model=self.local_provider.default_model,
                latency_ms=round(latency, 2),
                network_status=net_status,
                fallback_triggered=False,
                tokens_used=0
            )

    def get_system_status(self) -> Dict[str, Any]:
        """Provides status diagnostics of network and providers."""
        net = self.network.get_status()
        active_cloud = self.select_active_cloud_provider()

        providers_status = {
            "local_ollama": {
                "available": self.local_provider.is_available(),
                "endpoint": self.local_provider.endpoint,
                "model": self.local_provider.default_model
            },
            "cloud_providers": [
                {
                    "provider": p.get_provider_name(),
                    "configured": p.is_available()
                } for p in self.cloud_providers
            ]
        }

        return {
            "network_status": net,
            "active_route": "cloud" if (net == "ONLINE" and active_cloud) else "local_ollama",
            "active_cloud_provider": active_cloud.get_provider_name() if active_cloud else None,
            "providers": providers_status
        }

    def query(self, system_prompt: str, user_prompt: str) -> Tuple[bool, str]:
        """Convenience method matching AIRouter interface."""
        resp = self.generate(prompt=user_prompt, system_context=system_prompt)
        return bool(resp.content), resp.content


# ==============================================================================
# CLI Entrypoint for Testing / System Queries
# ==============================================================================
def main():
    router = ModelRouter()

    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("""AI OS Model Router CLI
Usage:
  ai-router --status                 # Display network and provider states
  ai-router --prompt "<query>"       # Execute query with automated routing
  ai-router --offline "<query>"      # Force query through local model
""")
        sys.exit(0)

    cmd = sys.argv[1].lower()
    if cmd in ("--status", "status"):
        print(json.dumps(router.get_system_status(), indent=2))
        sys.exit(0)

    elif cmd in ("--prompt", "-p"):
        if len(sys.argv) < 3:
            print("Usage: ai-router --prompt '<your request>'")
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        resp = router.generate(query)
        print(resp.to_json())

    elif cmd in ("--offline", "-o"):
        if len(sys.argv) < 3:
            print("Usage: ai-router --offline '<your request>'")
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        resp = router.generate(query, force_local=True)
        print(resp.to_json())

    else:
        # Default: treat whole argument as prompt
        query = " ".join(sys.argv[1:])
        resp = router.generate(query)
        print(resp.content)

if __name__ == "__main__":
    main()
