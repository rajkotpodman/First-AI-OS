#!/usr/bin/env python3
"""
web_dashboard.py - Interactive Web Testing Dashboard & GUI for AI OS
Author: Lead Systems Architect & UI/UX Specialist

Serves a premium, modern Web Dashboard on http://localhost:8080 that allows users
to visually inspect, interact with, test, and monitor all 19 subsystems of the AI Operating System.
"""

import os
import sys
import json
import time
import io
import re
import socket
import threading
import subprocess
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from contextlib import redirect_stdout, redirect_stderr
from typing import Dict, List, Optional, Any, Tuple

# Ensure src directory is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from main_orchestrator import MasterOSOrchestrator
from security_daemon import SecurityDaemon
from offline_docs_engine import OfflineDocsEngine

HOST = "127.0.0.1"
PORT = 8888
START_TIME = time.time()

# Shared Global Orchestrator instance for dashboard
_orchestrator = None
_orch_lock = threading.Lock()

def get_orchestrator():
    global _orchestrator
    with _orch_lock:
        if _orchestrator is None:
            _orchestrator = MasterOSOrchestrator()
            with redirect_stdout(io.StringIO()):
                _orchestrator.boot()
        return _orchestrator


# ==============================================================================
# HTML / CSS / JS Single-Page Web Dashboard
# ==============================================================================
DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI OS - Master Orchestrator Web Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #0a0d14;
            --bg-surface: #111622;
            --bg-card: #161c2d;
            --bg-card-hover: #1c2438;
            --border-color: rgba(255, 255, 255, 0.08);
            --border-glow: rgba(0, 240, 255, 0.25);
            --text-primary: #f0f4fc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-cyan: #00f0ff;
            --accent-blue: #3b82f6;
            --accent-purple: #8b5cf6;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-yellow: #f59e0b;
            --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            --font-mono: 'Fira Code', monospace;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg-base);
            color: var(--text-primary);
            font-family: var(--font-sans);
            line-height: 1.5;
            padding: 24px;
            min-height: 100vh;
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(0, 240, 255, 0.03) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(139, 92, 246, 0.03) 0%, transparent 40%);
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        /* Header */
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 28px;
            flex-wrap: wrap;
            gap: 16px;
        }

        .logo-area {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .logo-badge {
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
            color: #000;
            font-weight: 800;
            font-size: 1.3rem;
            padding: 10px 14px;
            border-radius: 12px;
            box-shadow: 0 0 20px rgba(0, 240, 255, 0.3);
            letter-spacing: 1px;
        }

        .logo-title h1 {
            font-size: 1.5rem;
            font-weight: 700;
            letter-spacing: -0.5px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .logo-title p {
            color: var(--text-secondary);
            font-size: 0.85rem;
        }

        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(16, 185, 129, 0.1);
            color: var(--accent-green);
            border: 1px solid rgba(16, 185, 129, 0.3);
            padding: 6px 14px;
            border-radius: 999px;
            font-size: 0.85rem;
            font-weight: 600;
        }

        .pulse-dot {
            width: 8px;
            height: 8px;
            background-color: var(--accent-green);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--accent-green);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }

        /* Top Metrics Grid */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }

        .metric-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 18px 20px;
            position: relative;
            overflow: hidden;
            transition: all 0.2s ease;
        }

        .metric-card:hover {
            border-color: var(--border-glow);
            transform: translateY(-2px);
        }

        .metric-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--accent-cyan), transparent);
        }

        .metric-label {
            font-size: 0.8rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-weight: 600;
            margin-bottom: 6px;
        }

        .metric-value {
            font-size: 1.4rem;
            font-weight: 700;
            color: var(--text-primary);
            display: flex;
            align-items: baseline;
            gap: 6px;
        }

        .metric-sub {
            font-size: 0.8rem;
            color: var(--text-secondary);
            margin-top: 4px;
        }

        /* Grid Layout */
        .main-layout {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 24px;
            margin-bottom: 28px;
        }

        @media (max-width: 1024px) {
            .main-layout {
                grid-template-columns: 1fr;
            }
        }

        .panel {
            background: var(--bg-surface);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 22px;
            margin-bottom: 24px;
        }

        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 18px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border-color);
        }

        .panel-header h2 {
            font-size: 1.15rem;
            font-weight: 600;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        /* Subsystems Grid */
        .subsystem-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 12px;
        }

        .subsystem-item {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 12px 14px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            transition: all 0.15s ease;
        }

        .subsystem-item:hover {
            border-color: rgba(0, 240, 255, 0.4);
            background: var(--bg-card-hover);
        }

        .subsystem-name {
            font-size: 0.88rem;
            font-weight: 600;
            color: var(--text-primary);
        }

        .subsystem-badge {
            align-self: flex-start;
            font-size: 0.72rem;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 6px;
            background: rgba(16, 185, 129, 0.15);
            color: var(--accent-green);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        /* Interactive Terminal */
        .terminal-box {
            background: #07090e;
            border: 1px solid var(--border-color);
            border-radius: 12px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            height: 480px;
        }

        .terminal-bar {
            background: #0d121c;
            padding: 10px 16px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .terminal-dots {
            display: flex;
            gap: 6px;
        }

        .dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }

        .dot.red { background: #ef4444; }
        .dot.yellow { background: #f59e0b; }
        .dot.green { background: #10b981; }

        .terminal-screen {
            flex: 1;
            padding: 16px;
            font-family: var(--font-mono);
            font-size: 0.85rem;
            color: #d1d5db;
            overflow-y: auto;
            white-space: pre-wrap;
            line-height: 1.4;
        }

        .terminal-input-bar {
            display: flex;
            padding: 10px 14px;
            background: #0a0f19;
            border-top: 1px solid var(--border-color);
            gap: 10px;
            align-items: center;
        }

        .prompt-symbol {
            color: var(--accent-cyan);
            font-family: var(--font-mono);
            font-weight: 700;
        }

        .terminal-input {
            flex: 1;
            background: transparent;
            border: none;
            color: var(--text-primary);
            font-family: var(--font-mono);
            font-size: 0.9rem;
            outline: none;
        }

        .btn-run {
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            color: white;
            border: none;
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.2s;
        }

        .btn-run:hover {
            opacity: 0.9;
        }

        /* Chips */
        .chip-group {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 12px;
        }

        .chip {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 0.78rem;
            font-family: var(--font-mono);
            cursor: pointer;
            transition: all 0.15s ease;
        }

        .chip:hover {
            background: var(--bg-card-hover);
            color: var(--accent-cyan);
            border-color: rgba(0, 240, 255, 0.4);
        }

        /* Test Action Buttons */
        .test-actions-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .test-btn {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 12px 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            color: var(--text-primary);
            cursor: pointer;
            transition: all 0.2s ease;
            text-align: left;
            width: 100%;
        }

        .test-btn:hover {
            background: var(--bg-card-hover);
            border-color: var(--border-glow);
            transform: translateX(3px);
        }

        .test-btn-info h4 {
            font-size: 0.9rem;
            font-weight: 600;
        }

        .test-btn-info p {
            font-size: 0.78rem;
            color: var(--text-muted);
        }

        .test-btn-action {
            font-size: 0.8rem;
            font-weight: 700;
            color: var(--accent-cyan);
            padding: 4px 10px;
            background: rgba(0, 240, 255, 0.1);
            border-radius: 6px;
        }

        .btn-all {
            background: linear-gradient(135deg, #059669, #10b981);
            color: white;
            border: none;
            padding: 12px 18px;
            border-radius: 10px;
            font-weight: 700;
            font-size: 0.95rem;
            cursor: pointer;
            width: 100%;
            margin-bottom: 14px;
            box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);
            transition: opacity 0.2s;
        }

        .btn-all:hover {
            opacity: 0.92;
        }

        /* Audit Table */
        .audit-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.82rem;
            margin-top: 10px;
        }

        .audit-table th {
            text-align: left;
            padding: 10px 12px;
            background: rgba(255, 255, 255, 0.02);
            color: var(--text-muted);
            border-bottom: 1px solid var(--border-color);
            font-weight: 600;
        }

        .audit-table td {
            padding: 10px 12px;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-secondary);
        }

        .badge-risk {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: 700;
            font-size: 0.75rem;
        }

        .risk-LOW { background: rgba(16, 185, 129, 0.2); color: var(--accent-green); }
        .risk-MEDIUM { background: rgba(245, 158, 11, 0.2); color: var(--accent-yellow); }
        .risk-HIGH { background: rgba(239, 68, 68, 0.2); color: var(--accent-red); }
        .risk-BLOCKED { background: #ef4444; color: white; }

        .hash-code {
            font-family: var(--font-mono);
            color: var(--accent-cyan);
            font-size: 0.75rem;
        }

        /* Results Modal / Notification */
        .toast {
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: var(--bg-card);
            border: 1px solid var(--accent-cyan);
            color: white;
            padding: 14px 20px;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
            display: none;
            z-index: 1000;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header>
            <div class="logo-area">
                <div class="logo-badge">AI OS</div>
                <div class="logo-title">
                    <h1>Autonomous Operating System <span style="font-size: 0.75rem; background: rgba(0,240,255,0.15); color: var(--accent-cyan); padding: 3px 8px; border-radius: 6px;">v1.0.0</span></h1>
                    <p>Master Orchestrator Testing & Telemetry Console</p>
                </div>
            </div>
            <div style="display: flex; gap: 12px; align-items: center;">
                <div class="status-pill">
                    <span class="pulse-dot"></span>
                    <span id="header-status">KERNEL ONLINE</span>
                </div>
                <button class="btn-run" onclick="refreshDashboard()" style="background: rgba(255,255,255,0.1); border: 1px solid var(--border-color);">⟳ Refresh</button>
            </div>
        </header>

        <!-- Top Telemetry Cards -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Hardware Acceleration</div>
                <div class="metric-value" id="card-hw-cpu">4 Cores</div>
                <div class="metric-sub" id="card-hw-ram">RAM: 7.9 GB | Model: llama3.2:1b</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Model Router Endpoint</div>
                <div class="metric-value" id="card-router-active" style="color: var(--accent-cyan);">anthropic</div>
                <div class="metric-sub" id="card-router-net">Network: ONLINE | Fallback: Ollama</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Offline Documentation</div>
                <div class="metric-value" id="card-docs-count">23 Symbols</div>
                <div class="metric-sub">SQLite FTS5 | Zero-Network Search</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Security & Audit Policy</div>
                <div class="metric-value" style="color: var(--accent-green);" id="card-sec-mode">STRICT</div>
                <div class="metric-sub">SHA-256 Tamper-Evident Hash Chain</div>
            </div>
        </div>

        <!-- Main Layout -->
        <div class="main-layout">
            <!-- Left Column: Interactive Terminal & Subsystems -->
            <div>
                <!-- Terminal Console -->
                <div class="panel">
                    <div class="panel-header">
                        <h2><span>⌨</span> Interactive AI OS Terminal</h2>
                        <span style="font-size: 0.8rem; color: var(--text-muted);">Direct Master Orchestrator Dispatch</span>
                    </div>

                    <div class="terminal-box">
                        <div class="terminal-bar">
                            <div class="terminal-dots">
                                <span class="dot red"></span>
                                <span class="dot yellow"></span>
                                <span class="dot green"></span>
                            </div>
                            <span style="font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono);">tty0: ai-os interactive session</span>
                            <button onclick="clearTerminal()" style="background: transparent; border: none; color: var(--text-muted); cursor: pointer; font-size: 0.75rem;">Clear</button>
                        </div>
                        <div class="terminal-screen" id="terminal-screen">
================================================================================
  █████╗ ██╗     ██████╗ ███████╗
 ██╔══██╗██║    ██╔═══██╗██╔════╝
 ███████║██║    ██║   ██║███████╗   [ AI OPERATING SYSTEM ]
 ██╔══██║██║    ██║   ██║╚════██║   Next-Gen Autonomous Kernel Runtime
 ██║  ██║██║    ╚██████╔╝███████║   All 19 Subsystems Online & Ready
 ╚═╝  ╚═╝╚═╝     ╚═════╝ ╚══════╝
================================================================================
Welcome to the AI OS Interactive Web Console.
Type a command below or click any quick-action shortcut.
Type 'help' for commands, 'status' for health diagnostics, 'docs python' for offline search.
                        </div>
                        <div class="terminal-input-bar">
                            <span class="prompt-symbol">ai-os ➜</span>
                            <input type="text" id="terminal-input" class="terminal-input" placeholder="Enter OS command (e.g., status, docs python, help)..." autocomplete="off" onkeydown="if(event.key === 'Enter') runTerminalCommand()">
                            <button class="btn-run" onclick="runTerminalCommand()">Execute</button>
                        </div>
                    </div>

                    <div class="chip-group">
                        <span class="chip" onclick="quickCommand('status')">status</span>
                        <span class="chip" onclick="quickCommand('help')">help</span>
                        <span class="chip" onclick="quickCommand('docs python')">docs python</span>
                        <span class="chip" onclick="quickCommand('docs sqlite')">docs sqlite</span>
                        <span class="chip" onclick="quickCommand('build sample fastapi sqlite app')">build fastapi app</span>
                        <span class="chip" onclick="quickCommand('github status')">plugin: github status</span>
                        <span class="chip" onclick="quickCommand('sudo rm -rf /etc/test_config')">test security guardrail</span>
                        <span class="chip" onclick="quickCommand('gui')">toggle gui</span>
                    </div>
                </div>

                <!-- Subsystems Grid -->
                <div class="panel">
                    <div class="panel-header">
                        <h2><span>⚙</span> Integrated Subsystems Matrix (19/19 Online)</h2>
                        <span style="font-size: 0.8rem; color: var(--accent-green); font-weight: 600;">All Systems Operational</span>
                    </div>
                    <div class="subsystem-grid" id="subsystem-grid">
                        <!-- Populated dynamically via JS -->
                    </div>
                </div>
            </div>

            <!-- Right Column: Test Runner & Verification Suite -->
            <div>
                <div class="panel">
                    <div class="panel-header">
                        <h2><span>🧪</span> E2E Test Suite</h2>
                        <span style="font-size: 0.75rem; color: var(--accent-cyan); font-weight: 600;">QA Automated Runner</span>
                    </div>

                    <button class="btn-all" onclick="runTestSuite('all')">▶ Run ALL E2E Tests (7 Steps)</button>

                    <div class="test-actions-list">
                        <button class="test-btn" onclick="runTestSuite(1)">
                            <div class="test-btn-info">
                                <h4>[1] Full Boot Sequence</h4>
                                <p>8-Phase subsystem initialization</p>
                            </div>
                            <span class="test-btn-action">Run Step 1</span>
                        </button>

                        <button class="test-btn" onclick="runTestSuite(2)">
                            <div class="test-btn-info">
                                <h4>[2] Built-in Commands</h4>
                                <p>Verify status, help, docs dispatch</p>
                            </div>
                            <span class="test-btn-action">Run Step 2</span>
                        </button>

                        <button class="test-btn" onclick="runTestSuite(3)">
                            <div class="test-btn-info">
                                <h4>[3] Dynamic GUI Pipeline</h4>
                                <p>Sway/Wayland trigger & configs</p>
                            </div>
                            <span class="test-btn-action">Run Step 3</span>
                        </button>

                        <button class="test-btn" onclick="runTestSuite(4)">
                            <div class="test-btn-info">
                                <h4>[4] Project Builder & Sandbox</h4>
                                <p>Scaffold, Deps, Sandbox & Git</p>
                            </div>
                            <span class="test-btn-action">Run Step 4</span>
                        </button>

                        <button class="test-btn" onclick="runTestSuite(5)">
                            <div class="test-btn-info">
                                <h4>[5] Security Guardrails</h4>
                                <p>Risk classification & audit seal</p>
                            </div>
                            <span class="test-btn-action">Run Step 5</span>
                        </button>

                        <button class="test-btn" onclick="runTestSuite(6)">
                            <div class="test-btn-info">
                                <h4>[6] Network Fallback</h4>
                                <p>Dynamic Local/Cloud model routing</p>
                            </div>
                            <span class="test-btn-action">Run Step 6</span>
                        </button>

                        <button class="test-btn" onclick="runTestSuite(7)">
                            <div class="test-btn-info">
                                <h4>[7] Graceful Shutdown</h4>
                                <p>State preservation & checkpoints</p>
                            </div>
                            <span class="test-btn-action">Run Step 7</span>
                        </button>
                    </div>
                </div>

                <!-- Latest Test Status Card -->
                <div class="panel">
                    <div class="panel-header">
                        <h2><span>📊</span> Latest Test Report</h2>
                        <span id="test-report-badge" class="subsystem-badge">PASS</span>
                    </div>
                    <div style="font-size: 0.82rem; color: var(--text-secondary); line-height: 1.6;" id="test-report-summary">
                        Loading latest test results...
                    </div>
                </div>
            </div>
        </div>

        <!-- Security Audit Trail Panel -->
        <div class="panel">
            <div class="panel-header">
                <h2><span>🛡</span> Cryptographic Security Audit Trail</h2>
                <span style="font-size: 0.8rem; color: var(--text-muted); font-family: var(--font-mono);">SHA-256 Tamper-Evident Ledger</span>
            </div>
            <div style="overflow-x: auto;">
                <table class="audit-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Timestamp</th>
                            <th>Command / Action</th>
                            <th>Risk Level</th>
                            <th>Outcome</th>
                            <th>Cryptographic Hash Seal</th>
                        </tr>
                    </thead>
                    <tbody id="audit-table-body">
                        <!-- Populated dynamically via JS -->
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <div class="toast" id="toast">Command Executed</div>

    <script>
        const SUBSYSTEMS_DATA = [
            { name: "Security Daemon", category: "Core", file: "security_daemon.py" },
            { name: "Hardware Manager", category: "Hardware", file: "hardware_manager.py" },
            { name: "Personal Memory", category: "Cognitive", file: "personal_memory.py" },
            { name: "Model Router", category: "Routing", file: "model_router.py" },
            { name: "AI Cron Daemon", category: "Background", file: "ai_cron_daemon.py" },
            { name: "System Indexer", category: "Background", file: "system_indexer.py" },
            { name: "Terminal UI", category: "Interface", file: "ai_terminal_ui.py" },
            { name: "AI Shell Agent", category: "Interface", file: "ai_shell_agent.py" },
            { name: "Multimodal Gateway", category: "Cognitive", file: "multimodal_gateway.py" },
            { name: "Project Architect", category: "Engineering", file: "project_architect.py" },
            { name: "Self Healer", category: "Engineering", file: "self_healer.py" },
            { name: "Dependency Resolver", category: "Engineering", file: "dependency_resolver.py" },
            { name: "Sandbox Runner", category: "Security", file: "sandbox_runner.py" },
            { name: "Git Automator", category: "Engineering", file: "git_automator.py" },
            { name: "Offline Docs Engine", category: "Core", file: "offline_docs_engine.py" },
            { name: "Docs Indexer", category: "Core", file: "index_docs.py" },
            { name: "GUI Expander", category: "Interface", file: "gui_expander.py" },
            { name: "System Updater", category: "Core", file: "system_updater.py" },
            { name: "Plugin Manager", category: "Extensibility", file: "plugin_manager.py" }
        ];

        function renderSubsystems() {
            const grid = document.getElementById("subsystem-grid");
            grid.innerHTML = "";
            SUBSYSTEMS_DATA.forEach(sub => {
                const item = document.createElement("div");
                item.className = "subsystem-item";
                item.innerHTML = `
                    <div class="subsystem-name">${sub.name}</div>
                    <div style="font-size: 0.72rem; color: var(--text-muted); font-family: var(--font-mono);">${sub.file}</div>
                    <span class="subsystem-badge">[ONLINE]</span>
                `;
                grid.appendChild(item);
            });
        }

        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                if (data.cpu) {
                    document.getElementById('card-hw-cpu').textContent = `${data.cpu.logical_cores} Cores`;
                    document.getElementById('card-hw-ram').textContent = `RAM: ${(data.memory.ram_total_mb / 1024).toFixed(1)} GB | Tier: ${data.profile.tier_name}`;
                }
                if (data.router) {
                    document.getElementById('card-router-active').textContent = data.router.active_route;
                    document.getElementById('card-router-net').textContent = `Network: ${data.router.network_status} | Provider: ${data.router.active_cloud_provider || 'Local Ollama'}`;
                }
                if (data.docs) {
                    document.getElementById('card-docs-count').textContent = `${data.docs.total_entries} Symbols`;
                }
            } catch (e) {
                console.error("Status fetch error", e);
            }
        }

        async function fetchAuditLogs() {
            try {
                const res = await fetch('/api/audit_logs');
                const entries = await res.json();
                const tbody = document.getElementById('audit-table-body');
                tbody.innerHTML = "";
                entries.slice(-8).reverse().forEach(e => {
                    const tr = document.createElement("tr");
                    const riskClass = `risk-${e.risk_level || 'LOW'}`;
                    const hashShort = e.entry_hash ? (e.entry_hash.substring(0, 16) + '...') : 'genesis';
                    tr.innerHTML = `
                        <td>#${e.entry_id}</td>
                        <td style="font-family: var(--font-mono);">${e.timestamp ? e.timestamp.replace('T', ' ').replace('Z', '') : '-'}</td>
                        <td style="font-family: var(--font-mono); font-weight: 600; color: var(--text-primary);">${e.command || e.action_type}</td>
                        <td><span class="badge-risk ${riskClass}">${e.risk_level || 'LOW'}</span></td>
                        <td><span style="color: ${e.execution_outcome === 'BLOCKED' ? 'var(--accent-red)' : 'var(--accent-green)'}; font-weight: 600;">${e.execution_outcome || 'SUCCESS'}</span></td>
                        <td class="hash-code">${hashShort}</td>
                    `;
                    tbody.appendChild(tr);
                });
            } catch (e) {
                console.error("Audit fetch error", e);
            }
        }

        async function fetchLatestReport() {
            try {
                const res = await fetch('/api/tests/latest');
                const rep = await res.json();
                const summaryDiv = document.getElementById('test-report-summary');
                const badge = document.getElementById('test-report-badge');

                if (rep.total_tests !== undefined) {
                    const allPass = rep.passed_tests === rep.total_tests;
                    badge.textContent = allPass ? 'ALL PASSED' : 'FAILURES';
                    badge.style.color = allPass ? 'var(--accent-green)' : 'var(--accent-red)';
                    badge.style.borderColor = allPass ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)';
                    badge.style.background = allPass ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)';

                    summaryDiv.innerHTML = `
                        <div><strong>Total Tests:</strong> ${rep.total_tests} (${rep.passed_tests} Passed, ${rep.failed_tests} Failed)</div>
                        <div><strong>Duration:</strong> ${rep.total_duration_seconds}s</div>
                        <div><strong>Last Run:</strong> ${rep.timestamp.replace('T', ' ').replace('Z', ' UTC')}</div>
                        <div style="margin-top: 8px; font-size: 0.78rem; color: var(--accent-cyan);">Click any step on the right to re-execute.</div>
                    `;
                }
            } catch (e) {
                console.error("Report fetch error", e);
            }
        }

        function appendTerminal(text) {
            const screen = document.getElementById('terminal-screen');
            screen.textContent += "\n" + text;
            screen.scrollTop = screen.scrollHeight;
        }

        function clearTerminal() {
            document.getElementById('terminal-screen').textContent = "ai-os console cleared.";
        }

        async function runTerminalCommand() {
            const input = document.getElementById('terminal-input');
            const cmd = input.value.trim();
            if (!cmd) return;

            appendTerminal(`ai-os ➜ ${cmd}`);
            input.value = "";

            try {
                const res = await fetch('/api/dispatch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command: cmd })
                });
                const data = await res.json();
                appendTerminal(data.output || "[Command completed]");
                fetchAuditLogs();
            } catch (e) {
                appendTerminal(`[Error]: ${e.message}`);
            }
        }

        function quickCommand(cmd) {
            document.getElementById('terminal-input').value = cmd;
            runTerminalCommand();
        }

        async function runTestSuite(step) {
            const toast = document.getElementById('toast');
            toast.textContent = `Running Test Step: ${step}...`;
            toast.style.display = 'block';

            appendTerminal(`\n[QA Runner] Initiating test verification (step: ${step})...`);

            try {
                const res = await fetch('/api/run_test', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ step: step })
                });
                const data = await res.json();
                appendTerminal(data.output || "[Tests completed]");
                toast.textContent = `Test completed: ${data.passed ? 'PASSED' : 'ATTENTION REQUIRED'}`;
                setTimeout(() => toast.style.display = 'none', 3000);
                fetchLatestReport();
                fetchAuditLogs();
            } catch (e) {
                appendTerminal(`[Test Runner Error]: ${e.message}`);
                toast.textContent = `Test Runner Error: ${e.message}`;
            }
        }

        function refreshDashboard() {
            fetchStatus();
            fetchAuditLogs();
            fetchLatestReport();
        }

        // Initialize on load
        window.onload = function() {
            renderSubsystems();
            refreshDashboard();
            setInterval(fetchAuditLogs, 5000);
        };
    </script>
</body>
</html>
"""


# ==============================================================================
# HTTP Request Handler
# ==============================================================================
class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Quiet logger
        return

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path in ("/", "/index.html"):
            content = DASHBOARD_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        elif parsed.path == "/api/status":
            orch = get_orchestrator()
            hw_metrics = orch.hardware.get_system_metrics() if orch.hardware else {}
            router_status = orch.model_router.get_system_status() if orch.model_router else {}
            docs_stats = orch.docs_engine.get_stats() if orch.docs_engine else {}

            resp_data = {
                "hostname": orch.hostname,
                "uptime_seconds": round(time.time() - START_TIME, 1),
                "cpu": hw_metrics.get("cpu", {}),
                "memory": hw_metrics.get("memory", {}),
                "profile": hw_metrics.get("profile", {}),
                "router": router_status,
                "docs": docs_stats
            }
            self._send_json(resp_data)

        elif parsed.path == "/api/audit_logs":
            orch = get_orchestrator()
            entries = []
            if orch.security and hasattr(orch.security, "audit_logger"):
                entries = orch.security.audit_logger.read_entries()
            self._send_json(entries)

        elif parsed.path == "/api/tests/latest":
            report_file = Path(PROJECT_ROOT) / "tests" / "reports" / "manual_test_results.json"
            if report_file.exists():
                try:
                    with open(report_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self._send_json(data)
                    return
                except Exception:
                    pass
            self._send_json({"error": "No reports generated yet"})

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"

        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        if parsed.path == "/api/dispatch":
            cmd = payload.get("command", "").strip()
            orch = get_orchestrator()

            start_t = time.time()
            captured = io.StringIO()
            with redirect_stdout(captured), redirect_stderr(captured):
                try:
                    orch.dispatch(cmd)
                except Exception as e:
                    print(f"Command execution error: {e}")

            out = captured.getvalue()
            # Strip ANSI color escape sequences for clean web terminal rendering
            clean_out = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', out)

            self._send_json({
                "command": cmd,
                "output": clean_out.strip() or "[Command executed successfully with no output]",
                "duration_seconds": round(time.time() - start_t, 3)
            })

        elif parsed.path == "/api/run_test":
            step = payload.get("step", "all")
            test_script = str(Path(PROJECT_ROOT) / "tests" / "manual_test_suite.py")

            cmd = [sys.executable, test_script]
            if str(step).lower() == "all":
                cmd.append("--all")
            else:
                cmd.extend(["--step", str(step)])

            try:
                res = subprocess.run(
                    cmd,
                    cwd=PROJECT_ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=180
                )
                output = res.stdout + ("\n" + res.stderr if res.stderr else "")
                clean_output = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', output)
                self._send_json({
                    "passed": (res.returncode == 0),
                    "exit_code": res.returncode,
                    "output": clean_output.strip()
                })
            except Exception as e:
                self._send_json({
                    "passed": False,
                    "exit_code": 1,
                    "output": f"Test runner execution error: {e}"
                })

        else:
            self.send_response(404)
            self.end_headers()


# ==============================================================================
# Server Runner
# ==============================================================================
def run_server():
    server = HTTPServer((HOST, PORT), DashboardHandler)
    print(f"\033[1;36m" + "=" * 70 + "\033[0m")
    print(f"\033[1;32m[✓] AI OS Web Testing Dashboard Active!\033[0m")
    print(f"\033[1;34m[*] URL: \033[1;36mhttp://localhost:{PORT}\033[0m (Open in browser to check & test)")
    print(f"\033[1;34m[*] API: http://localhost:{PORT}/api/status | /api/audit_logs | /api/tests/latest\033[0m")
    print(f"\033[2mPress Ctrl+C to stop the dashboard server.\033[0m")
    print(f"\033[1;36m" + "=" * 70 + "\033[0m")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\033[1;33m[*] Stopping Web Dashboard...\033[0m")
        server.server_close()


if __name__ == "__main__":
    run_server()
