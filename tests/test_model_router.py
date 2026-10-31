#!/usr/bin/env python3
"""
test_model_router.py - Unit tests for Hybrid AI Router & Network Fallback Subsystem
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from model_router import (
    NetworkMonitor,
    TaskClassifier,
    ModelRequest,
    ModelResponse,
    OllamaProvider,
    OpenAIProvider,
    AnthropicProvider,
    ModelRouter
)

class TestNetworkMonitor(unittest.TestCase):
    """Test network probe and forced override states."""

    def test_forced_mode_offline(self):
        monitor = NetworkMonitor()
        monitor.set_forced_mode("offline")
        self.assertEqual(monitor.get_status(), "OFFLINE")
        self.assertFalse(monitor.is_online())

    def test_forced_mode_online(self):
        monitor = NetworkMonitor()
        monitor.set_forced_mode("online")
        self.assertEqual(monitor.get_status(), "ONLINE")
        self.assertTrue(monitor.is_online())

class TestTaskClassifier(unittest.TestCase):
    """Test task complexity and privacy heuristic classification."""

    def test_privacy_detection(self):
        queries = [
            "What is my root password?",
            "Read the private key in ~/.ssh/id_rsa",
            "Generate an API_KEY token for authentication",
            "Inspect /etc/shadow"
        ]
        for q in queries:
            classification = TaskClassifier.classify(q)
            self.assertEqual(classification, "privacy_sensitive", f"Failed to flag privacy in: '{q}'")

    def test_simple_task_detection(self):
        queries = [
            "How do I use grep to find a word?",
            "Explain ls -la",
            "What is the date today?",
            "Echo hello world"
        ]
        for q in queries:
            classification = TaskClassifier.classify(q)
            self.assertEqual(classification, "simple", f"Failed simple task check: '{q}'")

    def test_complex_task_detection(self):
        queries = [
            "Architect and build a full-stack real-time chat application with WebSockets",
            "Refactor entire concurrency model in rust",
            "Design a distributed system for fault-tolerant telemetry"
        ]
        for q in queries:
            classification = TaskClassifier.classify(q)
            self.assertEqual(classification, "complex", f"Failed complex task check: '{q}'")

class TestModelRouterExecution(unittest.TestCase):
    """Test routing decisions, cloud invocation, and local failover."""

    def setUp(self):
        self.mock_net = NetworkMonitor()
        self.router = ModelRouter(network_monitor=self.mock_net)

        # Mock providers
        self.mock_local = MagicMock()
        self.mock_local.get_provider_name.return_value = "ollama"
        self.mock_local.default_model = "llama3.2:3b"
        self.mock_local.execute_request.return_value = (True, "Local response", {"model": "llama3.2:3b", "tokens": 20})

        self.mock_cloud = MagicMock()
        self.mock_cloud.get_provider_name.return_value = "anthropic"
        self.mock_cloud.is_available.return_value = True
        self.mock_cloud.execute_request.return_value = (True, "Cloud Claude response", {"model": "claude-3-5-sonnet", "tokens": 80})

        self.router.local_provider = self.mock_local
        self.router.cloud_providers = [self.mock_cloud]

    def test_offline_mode_routes_to_local(self):
        self.mock_net.set_forced_mode("offline")
        resp = self.router.generate("Architect and build a full-stack real-time app")

        self.assertEqual(resp.provider, "ollama")
        self.assertEqual(resp.network_status, "OFFLINE")
        self.assertFalse(resp.fallback_triggered)
        self.mock_local.execute_request.assert_called_once()
        self.mock_cloud.execute_request.assert_not_called()

    def test_online_simple_task_routes_to_local(self):
        self.mock_net.set_forced_mode("online")
        resp = self.router.generate("What is the command to list files?")

        self.assertEqual(resp.provider, "ollama")
        self.assertFalse(resp.fallback_triggered)
        self.mock_local.execute_request.assert_called_once()
        self.mock_cloud.execute_request.assert_not_called()

    def test_online_privacy_task_routes_to_local(self):
        self.mock_net.set_forced_mode("online")
        resp = self.router.generate("Save my password and api_key")

        self.assertEqual(resp.provider, "ollama")
        self.mock_local.execute_request.assert_called_once()
        self.mock_cloud.execute_request.assert_not_called()

    def test_online_complex_task_routes_to_cloud(self):
        self.mock_net.set_forced_mode("online")
        resp = self.router.generate("Architect and build a full-stack real-time application")

        self.assertEqual(resp.provider, "anthropic")
        self.assertEqual(resp.network_status, "ONLINE")
        self.assertFalse(resp.fallback_triggered)
        self.mock_cloud.execute_request.assert_called_once()

    def test_cloud_failure_triggers_automatic_local_fallback(self):
        self.mock_net.set_forced_mode("online")
        # Simulate Cloud 500 error or rate limit
        self.mock_cloud.execute_request.return_value = (False, "HTTP 429: Too Many Requests", {})

        resp = self.router.generate("Architect and build a full-stack distributed system")

        # Must fall back to local Ollama
        self.assertEqual(resp.provider, "ollama")
        self.assertTrue(resp.fallback_triggered)
        self.assertIn("HTTP 429", resp.fallback_reason)
        self.assertEqual(resp.content, "Local response")
        self.mock_local.execute_request.assert_called_once()

if __name__ == "__main__":
    unittest.main()
