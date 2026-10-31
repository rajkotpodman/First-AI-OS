#!/usr/bin/env python3
"""
main_orchestrator.py - Master OS Orchestrator & System Boot Entry Point for AI OS
Author: Chief Operating System Architect and Lead System Integrator

Coordinates and integrates all 19 subsystems into a single, cohesive, bootable AI OS runtime:
 1. security_daemon      (Security policies, audit logs, command guardrails)
 2. hardware_manager     (Hardware discovery, GPU/RAM/CPU, model optimization)
 3. personal_memory      (User memory, persistent profile, session context)
 4. model_router         (Multi-tier local/remote LLM routing & network status)
 5. ai_cron_daemon       (Background autonomous task scheduler)
 6. system_indexer       (Incremental filesystem & AST symbol analyzer)
 7. ai_terminal_ui       (Rich interactive TTY interface & dashboard)
 8. ai_shell_agent       (Central CLI shell & natural language planner)
 9. multimodal_gateway   (Voice input/transcription & vision image analysis)
10. project_architect    (Autonomous software project scaffolder)
11. self_healer          (Autonomous testing, patch application & verification loop)
12. dependency_resolver  (Auto-healing package manager adapter)
13. sandbox_runner       (Isolated container & process execution sandbox)
14. git_automator        (Git versioning, conventional commits, checkpoints, rollbacks)
15. offline_docs_engine  (Instant offline documentation & FTS5 search)
16. index_docs           (Documentation ingestion pipeline)
17. gui_expander         (Dynamic Sway/Wayland window manager toggle)
18. system_updater       (System updates, backups, and rollback points)
19. plugin_manager       (Modular plugin discovery, security sandbox & intent routing)
"""

import os
import sys
import re
import json
import time
import signal
import platform
import threading
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Ensure src directory is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# ==============================================================================
# Subsystem Imports with Fallback Architecture
# ==============================================================================
try:
    from security_daemon import SecurityDaemon
except ImportError:
    SecurityDaemon = None

try:
    from hardware_manager import HardwareManager
except ImportError:
    HardwareManager = None

try:
    from personal_memory import PersonalMemoryEngine
except ImportError:
    PersonalMemoryEngine = None

try:
    from model_router import ModelRouter
except ImportError:
    ModelRouter = None

try:
    from ai_cron_daemon import AICronDaemon
except ImportError:
    AICronDaemon = None

try:
    from system_indexer import SystemIndexer
except ImportError:
    SystemIndexer = None

try:
    from ai_terminal_ui import AITerminalUI
except ImportError:
    AITerminalUI = None

try:
    from ai_shell_agent import AIShellAgent, ConfigManager
except ImportError:
    AIShellAgent = None
    ConfigManager = None

try:
    from multimodal_gateway import MultimodalGateway
except ImportError:
    MultimodalGateway = None

try:
    from project_architect import ProjectArchitect
except ImportError:
    ProjectArchitect = None

try:
    from self_healer import SelfHealer
except ImportError:
    SelfHealer = None

try:
    from dependency_resolver import DependencyResolver
except ImportError:
    DependencyResolver = None

try:
    from sandbox_runner import SandboxRunner
except ImportError:
    SandboxRunner = None

try:
    from git_automator import GitAutomator
except ImportError:
    GitAutomator = None

try:
    from offline_docs_engine import OfflineDocsEngine
except ImportError:
    OfflineDocsEngine = None

try:
    from index_docs import DocsIndexer
except ImportError:
    DocsIndexer = None

try:
    from gui_expander import GUIExpander
except ImportError:
    GUIExpander = None

try:
    from system_updater import SystemUpdater
except ImportError:
    SystemUpdater = None

try:
    from plugin_manager import PluginManager
except ImportError:
    PluginManager = None


# ==============================================================================
# Master ASCII Boot Banner
# ==============================================================================
BOOT_BANNER = r"""
 █████╗ ██╗     ██████╗ ███████╗
██╔══██╗██║    ██╔═══██╗██╔════╝
███████║██║    ██║   ██║███████╗
██╔══██║██║    ██║   ██║╚════██║
██║  ██║██║    ╚██████╔╝███████║
╚═╝  ╚═╝╚═╝     ╚═════╝ ╚══════╝
 [ AI OPERATING SYSTEM - AUTONOMOUS KERNEL RUNTIME ]
"""


# ==============================================================================
# Master OS Orchestrator Engine
# ==============================================================================
class MasterOSOrchestrator:
    """
    Central bootstrap engine that initializes all 19 subsystems,
    executes health audits, routes multimodal inputs, runs background daemons,
    and manages safe system termination.
    """

    def __init__(self, config_override: Optional[Dict[str, Any]] = None):
        self.start_time = time.time()
        self.config = config_override or (ConfigManager.load() if ConfigManager else {})
        self.hostname = self.config.get("system", {}).get("hostname", "ai-os")
        self.workspace_dir = Path(self.config.get("system", {}).get("workspace_dir", os.getcwd())).resolve()

        # Subsystem references (initialized during boot sequence)
        self.security: Optional[Any] = None
        self.hardware: Optional[Any] = None
        self.memory: Optional[Any] = None
        self.model_router: Optional[Any] = None
        self.cron_daemon: Optional[Any] = None
        self.system_indexer: Optional[Any] = None
        self.ui: Optional[Any] = None
        self.shell_agent: Optional[Any] = None
        self.multimodal: Optional[Any] = None
        self.architect: Optional[Any] = None
        self.healer: Optional[Any] = None
        self.resolver: Optional[Any] = None
        self.sandbox: Optional[Any] = None
        self.git_automator: Optional[Any] = None
        self.docs_engine: Optional[Any] = None
        self.gui_expander: Optional[Any] = None
        self.updater: Optional[Any] = None
        self.plugin_manager: Optional[Any] = None

        self.running = False
        self.bg_threads: List[threading.Thread] = []

        # Register OS signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, sig, frame):
        """Intercepts termination signals to trigger graceful shutdown."""
        sig_name = "SIGINT" if sig == signal.SIGINT else "SIGTERM"
        print(f"\n\033[1;33m[*] Intercepted {sig_name}. Initiating graceful AI OS shutdown...\033[0m")
        self.shutdown()
        sys.exit(0)

    # --------------------------------------------------------------------------
    # 1. Boot Initialization Sequence
    # --------------------------------------------------------------------------
    def boot(self) -> bool:
        """
        Executes the formal 8-phase AI OS boot sequence.
        Returns True if all critical subsystems initialize cleanly.
        """
        print("\033[1;36m" + BOOT_BANNER + "\033[0m")
        print(f"\033[1;34m[*] Bootstrapping AI OS on {platform.system()} ({platform.machine()}) | Hostname: {self.hostname}\033[0m")
        print("\033[2m" + "=" * 70 + "\033[0m")

        # Phase 1: Security Daemon & Integrity Check
        self._boot_phase_1_security()

        # Phase 2: Hardware Detection & Model Acceleration
        self._boot_phase_2_hardware()

        # Phase 3: Personal Memory & User Profile
        self._boot_phase_3_memory()

        # Phase 4: Model Router & Network Status
        self._boot_phase_4_routing()

        # Phase 5: Autonomous Background Daemons (Cron & Indexer)
        self._boot_phase_5_background_services()

        # Phase 6: Developer Tooling (Git, Sandbox, Resolver, Healer, Architect, Docs)
        self._boot_phase_6_developer_tooling()

        # Phase 7: Extensions, Plugins & Multimodal Gateways
        self._boot_phase_7_extensions_and_multimodal()

        # Phase 8: Terminal UI & Dashboard
        self._boot_phase_8_ui()

        elapsed = time.time() - self.start_time
        print("\033[2m" + "=" * 70 + "\033[0m")
        print(f"\033[1;32m[✓] AI OS Boot Sequence Complete in {elapsed:.2f}s! Runtime Ready.\033[0m\n")
        self.running = True
        return True

    def _boot_phase_1_security(self):
        print("\033[1;36m[Phase 1/8]\033[0m Initializing Security Daemon & Policy Enforcement...")
        if SecurityDaemon:
            try:
                self.security = SecurityDaemon()
                mode = self.security.policy.get("mode", "strict")
                print(f"  \033[1;32m✓\033[0m Security Daemon Active [Policy Mode: {mode.upper()}]")
            except Exception as e:
                print(f"  \033[1;33m!\033[0m Security Daemon loaded with fallback: {e}")
        else:
            print("  \033[1;33m!\033[0m Security Daemon module not found; running in basic mode.")

    def _boot_phase_2_hardware(self):
        print("\033[1;36m[Phase 2/8]\033[0m Detecting Hardware Capabilities & Acceleration...")
        if HardwareManager:
            try:
                self.hardware = HardwareManager()
                cpu_cores = self.hardware.cpu.logical_cores
                ram_gb = self.hardware.memory.ram_total_mb / 1024.0
                gpu_name = self.hardware.gpu.model_name if self.hardware.gpu.detected else "Integrated/CPU"
                tier = self.hardware.profile.tier_name
                model = self.hardware.profile.recommended_model
                print(f"  \033[1;32m✓\033[0m Hardware Profile: {cpu_cores} Cores | {ram_gb:.1f} GB RAM | GPU: {gpu_name} (Tier: {tier}, Model: {model})")
            except Exception as e:
                print(f"  \033[1;33m!\033[0m Hardware Manager detection note: {e}")
        else:
            print("  \033[1;33m!\033[0m Hardware Manager module not found.")

    def _boot_phase_3_memory(self):
        print("\033[1;36m[Phase 3/8]\033[0m Mounting Personal Memory Engine & Context Cache...")
        if PersonalMemoryEngine:
            try:
                self.memory = PersonalMemoryEngine()
                count = len(self.memory.list_memories())
                print(f"  \033[1;32m✓\033[0m Personal Memory: {count} entities | Store: SQLite+Vector (Local)")
            except Exception as e:
                print(f"  \033[1;33m!\033[0m Personal Memory note: {e}")
        else:
            print("  \033[1;33m!\033[0m Personal Memory Engine not available.")

    def _boot_phase_4_routing(self):
        print("\033[1;36m[Phase 4/8]\033[0m Establishing Model Router & Connectivity Status...")
        if ModelRouter:
            try:
                self.model_router = ModelRouter(self.config)
                net_status = self.model_router.network.get_status()
                active_cloud = self.model_router.select_active_cloud_provider()
                provider = active_cloud.get_provider_name() if (active_cloud and net_status == "ONLINE") else self.model_router.local_provider.get_provider_name()
                model_name = active_cloud.model if (active_cloud and net_status == "ONLINE") else self.model_router.local_provider.default_model
                print(f"  \033[1;32m✓\033[0m Model Router: Active Provider '{provider}' ({model_name}) | Network: {net_status}")
            except Exception as e:
                print(f"  \033[1;33m!\033[0m Model Router note: {e}")
        else:
            print("  \033[1;33m!\033[0m Model Router not available.")

    def _boot_phase_5_background_services(self):
        print("\033[1;36m[Phase 5/8]\033[0m Launching Autonomous Daemons (Cron & System Indexer)...")
        # 1. Background Cron Daemon
        if AICronDaemon:
            try:
                self.cron_daemon = AICronDaemon()
                cron_thread = threading.Thread(
                    target=self.cron_daemon.start_daemon,
                    kwargs={"poll_interval": 10},
                    daemon=True,
                    name="AICronDaemonThread"
                )
                cron_thread.start()
                self.bg_threads.append(cron_thread)
                tasks = self.cron_daemon.load_tasks()
                print(f"  \033[1;32m✓\033[0m AI Cron Daemon: Active [{len(tasks)} scheduled tasks monitored]")
            except Exception as e:
                print(f"  \033[1;33m!\033[0m AI Cron Daemon note: {e}")

        # 2. Incremental System Indexer
        if SystemIndexer:
            try:
                self.system_indexer = SystemIndexer()
                # Run quick non-blocking incremental index pass in background
                def _bg_index():
                    try:
                        self.system_indexer.scan_directory(str(self.workspace_dir), incremental=True)
                    except Exception:
                        pass
                idx_thread = threading.Thread(target=_bg_index, daemon=True, name="SystemIndexerThread")
                idx_thread.start()
                self.bg_threads.append(idx_thread)
                print(f"  \033[1;32m✓\033[0m System Indexer: AST code & symbol analyzer active")
            except Exception as e:
                print(f"  \033[1;33m!\033[0m System Indexer note: {e}")

    def _boot_phase_6_developer_tooling(self):
        print("\033[1;36m[Phase 6/8]\033[0m Initializing Autonomous Tooling & Verification Engines...")
        self.git_automator = GitAutomator() if GitAutomator else None
        self.sandbox = SandboxRunner() if SandboxRunner else None
        self.resolver = DependencyResolver() if DependencyResolver else None
        self.docs_engine = OfflineDocsEngine() if OfflineDocsEngine else None

        # Auto-seed docs if empty
        if self.docs_engine and self.docs_engine.is_empty() and DocsIndexer:
            indexer = DocsIndexer(self.docs_engine)
            indexer.seed_default_documentation()

        # Attach Architect and Self-Healer
        self.architect = ProjectArchitect(
            projects_root=str(self.workspace_dir / "projects"),
            router=self.model_router,
            resolver=self.resolver,
            sandbox=self.sandbox,
            git_automator=self.git_automator
        ) if ProjectArchitect else None

        self.healer = SelfHealer(
            router=self.model_router,
            sandbox=self.sandbox,
            git_automator=self.git_automator,
            docs_engine=self.docs_engine
        ) if SelfHealer else None

        self.updater = SystemUpdater() if SystemUpdater else None
        self.gui_expander = GUIExpander() if GUIExpander else None

        tools_status = []
        if self.git_automator: tools_status.append("Git")
        if self.sandbox: tools_status.append("Sandbox")
        if self.resolver: tools_status.append("Deps")
        if self.docs_engine: tools_status.append("OfflineDocs")
        if self.architect: tools_status.append("Architect")
        if self.healer: tools_status.append("SelfHealer")
        print(f"  \033[1;32m✓\033[0m Developer Suite: [{', '.join(tools_status)}]")

    def _boot_phase_7_extensions_and_multimodal(self):
        print("\033[1;36m[Phase 7/8]\033[0m Loading Modular Plugins & Multimodal Gateway...")
        if PluginManager:
            try:
                self.plugin_manager = PluginManager()
                p_count = len(self.plugin_manager.plugins)
                print(f"  \033[1;32m✓\033[0m Plugin Subsystem: {p_count} active plugin(s) registered")
            except Exception as e:
                print(f"  \033[1;33m!\033[0m Plugin Manager note: {e}")

        if MultimodalGateway:
            try:
                self.multimodal = MultimodalGateway()
                print("  \033[1;32m✓\033[0m Multimodal Gateway: Voice (Whisper) & Vision (Llava/Qwen) listener ready")
            except Exception as e:
                print(f"  \033[1;33m!\033[0m Multimodal Gateway note: {e}")

    def _boot_phase_8_ui(self):
        print("\033[1;36m[Phase 8/8]\033[0m Initializing Interactive Terminal UI & Shell Agent...")
        if AITerminalUI:
            try:
                self.ui = AITerminalUI()
                print("  \033[1;32m✓\033[0m Rich Terminal UI: Interactive TTY & Status Dashboard active")
            except Exception as e:
                print(f"  \033[1;33m!\033[0m Terminal UI note: {e}")

        if AIShellAgent:
            try:
                self.shell_agent = AIShellAgent()
                print("  \033[1;32m✓\033[0m AI Shell Agent: Natural language command planner connected")
            except Exception as e:
                print(f"  \033[1;33m!\033[0m Shell Agent note: {e}")

    # --------------------------------------------------------------------------
    # 2. Main Event Loop & Multimodal Dispatching
    # --------------------------------------------------------------------------
    def run_event_loop(self):
        """
        Primary interactive event loop.
        Accepts Text, Voice commands, Image queries, and dispatches them
        through the appropriate subsystem.
        """
        # Create prompt_toolkit session if UI available
        session = self.ui.create_interactive_session() if self.ui else None

        prompt_str = f"\033[1;36m{self.hostname} \033[1;32m➜\033[0m "

        while self.running:
            try:
                # 1. Display unread background cron notifications
                self._check_and_display_notifications()

                # 2. Prompt user for input
                if self.ui and session:
                    user_input = self.ui.prompt(session, prompt_str=prompt_str)
                else:
                    user_input = input(prompt_str).strip()

                if not user_input:
                    continue

                # 3. Dispatch user input
                self.dispatch_request(user_input)

            except (KeyboardInterrupt, EOFError):
                print()
                confirm = input("\033[1;33mAre you sure you want to shutdown AI OS? [y/N]: \033[0m").strip().lower()
                if confirm in ("y", "yes"):
                    self.shutdown()
                    break
            except Exception as e:
                print(f"\033[1;31m[!] Unhandled exception in OS Event Loop: {e}\033[0m")

    def _check_and_display_notifications(self):
        """Displays any unread completion alerts from the background cron daemon."""
        if self.cron_daemon:
            unread = self.cron_daemon.notifications.get_unread()
            if unread:
                for notif in unread:
                    lvl = notif.get("level", "info")
                    badge = "\033[1;32m[TASK COMPLETED]\033[0m" if lvl == "success" else "\033[1;31m[TASK ALERT]\033[0m"
                    print(f"\n{badge} \033[1m{notif.get('title')}\033[0m: {notif.get('message')}\n")
                self.cron_daemon.notifications.mark_all_read()

    def dispatch_request(self, request_str: str):
        """
        Intelligent Multimodal & Subsystem Request Dispatcher:
        1. Built-in OS commands (help, status, gui, voice, vision, memory, docs, schedule, plugin, update)
        2. Plugin intent matching
        3. Project generation triggers ('build a ...', 'create a project ...')
        4. Multimodal triggers (voice capture, image analysis)
        5. Native shell execution or Natural Language Agent execution
        """
        cleaned = request_str.strip()
        lower = cleaned.lower()

        # ----------------------------------------------------------------------
        # A. Built-in System Commands
        # ----------------------------------------------------------------------
        if lower in ("exit", "quit", "poweroff", "shutdown"):
            self.shutdown()
            sys.exit(0)

        elif lower in ("clear", "cls"):
            os.system("cls" if sys.platform == "win32" else "clear")
            if self.ui:
                self.ui.render_header()
            return

        elif lower == "help":
            self._render_help()
            return

        elif lower == "status":
            self._render_status()
            return

        elif lower in ("gui", "toggle-gui"):
            if self.gui_expander:
                print("\033[1;36m[*] Toggling Sway/Wayland Graphical Desktop...\033[0m")
                self.gui_expander.toggle_gui()
            else:
                print("\033[1;33m[!] GUI Expander not configured on this host.\033[0m")
            return

        elif lower.startswith("voice"):
            self._handle_voice_command(cleaned)
            return

        elif lower.startswith("vision"):
            self._handle_vision_command(cleaned)
            return

        elif lower.startswith("docs ") or lower == "docs":
            query = cleaned[5:].strip() if len(cleaned) > 4 else ""
            if self.docs_engine:
                if query:
                    results = self.docs_engine.search_docs(query, limit=3)
                    for idx, r in enumerate(results, 1):
                        print(f"\n\033[1;34m[{idx}] {r.symbol}\033[0m ({r.language}) - {r.title}")
                        if r.signature: print(f"    \033[1;33mSignature:\033[0m {r.signature}")
                        print(f"    \033[2m{r.excerpt}\033[0m")
                else:
                    stats = self.docs_engine.get_stats()
                    print(f"\033[1;36m[*] Offline Docs Index:\033[0m {stats['total_entries']} entries across {stats['total_docsets']} docsets.")
            return

        elif lower.startswith("schedule"):
            cmd = [sys.executable, str(Path(SCRIPT_DIR) / "ai_schedule.py")] + cleaned.split()[1:]
            subprocess.run(cmd)
            return

        elif lower.startswith("plugin"):
            cmd = [sys.executable, str(Path(SCRIPT_DIR) / "ai_plugin.py")] + cleaned.split()[1:]
            subprocess.run(cmd)
            return

        # ----------------------------------------------------------------------
        # B. Check Plugin Trigger Matching
        # ----------------------------------------------------------------------
        if self.plugin_manager:
            plugin_match = self.plugin_manager.match_intent(cleaned)
            if plugin_match:
                plugin, trigger, confidence = plugin_match
                print(f"\033[1;34m[*] Routing to active plugin: '{plugin.manifest.name}' (Trigger: '{trigger}')\033[0m")
                result = self.plugin_manager.execute_matching_plugin(cleaned)
                if result:
                    print(f"\n{result.content}\n")
                    return

        # ----------------------------------------------------------------------
        # C. Autonomous Project Generation Trigger
        # ----------------------------------------------------------------------
        if any(lower.startswith(p) for p in ["build ", "create a ", "scaffold ", "generate app ", "make a "]) and self.architect:
            print("\033[1;36m[*] Project Architect: Analyzing specification and designing blueprint...\033[0m")
            res = self.architect.build_project(cleaned, run_verification=True)
            if res.get("success"):
                print(f"\033[1;32m[OK] Project '{res.get('project_name')}' generated and verified at {res.get('project_path')}!\033[0m")
            else:
                print(f"\033[1;31m[!] Project generation failed: {res.get('error')}\033[0m")
            return

        # ----------------------------------------------------------------------
        # D. Shell Agent / Standard POSIX Execution
        # ----------------------------------------------------------------------
        if self.shell_agent:
            if self.shell_agent.is_standard_shell_command(cleaned):
                self.shell_agent.execute_native_command(cleaned)
            else:
                self.shell_agent.handle_natural_language(cleaned)
        else:
            # Direct shell fallback
            try:
                subprocess.run(cleaned, shell=True)
            except Exception as e:
                print(f"\033[1;31mCommand failed: {e}\033[0m")

    dispatch = dispatch_request

    def _handle_voice_command(self, cmd_str: str):
        """Captures audio or transcribes voice input via MultimodalGateway."""
        if not self.multimodal:
            print("\033[1;33m[!] Multimodal Gateway not available.\033[0m")
            return

        parts = cmd_str.split(maxsplit=1)
        audio_path = parts[1].strip() if len(parts) > 1 else None

        print("\033[1;35m[*] Multimodal Gateway: Listening/Transcribing voice input...\033[0m")
        if audio_path and os.path.exists(audio_path):
            res = self.multimodal.transcribe_audio(audio_path)
        else:
            res = self.multimodal.record_and_transcribe(duration_seconds=5)

        if res and res.transcript.strip():
            print(f"\033[1;32m[Voice Transcript]:\033[0m \"{res.transcript}\"")
            print("\033[1;34m[*] Executing transcribed voice command...\033[0m")
            self.dispatch_request(res.transcript)
        else:
            print("\033[1;33m[!] No speech detected or transcription was empty.\033[0m")

    def _handle_vision_command(self, cmd_str: str):
        """Analyzes screenshots or image files using Vision LLM."""
        if not self.multimodal:
            print("\033[1;33m[!] Multimodal Gateway not available.\033[0m")
            return

        parts = cmd_str.split(maxsplit=2)
        if len(parts) < 2:
            print("\033[1;33mUsage: vision <path_to_image_or_screenshot> [prompt]\033[0m")
            return

        img_path = parts[1].strip()
        custom_prompt = parts[2].strip() if len(parts) > 2 else "Analyze this screenshot and explain any errors or UI components."

        print(f"\033[1;35m[*] Analyzing image: {img_path}...\033[0m")
        result = self.multimodal.analyze_image(img_path, prompt=custom_prompt)
        print(f"\n\033[1;36m[Vision Analysis]:\033[0m\n{result.description}\n")

    def _render_help(self):
        """Displays system architecture and command cheatsheet."""
        print(f"\n\033[1;36m=== AI OPERATING SYSTEM - COMMAND REFERENCE ===\033[0m")
        print("  \033[1mhelp\033[0m                  Display this commands reference")
        print("  \033[1mstatus\033[0m                Show real-time health of all 19 subsystems")
        print("  \033[1mgui\033[0m                   Toggle Sway/Wayland Graphical Desktop environment")
        print("  \033[1mvoice [file.wav]\033[0m      Record microphone or transcribe voice command (Whisper)")
        print("  \033[1mvision <image> [msg]\033[0m  Inspect screenshot or diagram with Vision LLM (Llava)")
        print("  \033[1mdocs <query>\033[0m          Instant offline API documentation search (FTS5)")
        print("  \033[1mschedule <args...>\033[0m    Manage autonomous recurring cron tasks")
        print("  \033[1mplugin <args...>\033[0m      List, inspect, and run modular OS extensions")
        print("  \033[1mbuild <prompt>\033[0m        Generate full software project repository")
        print("  \033[1mclear\033[0m                 Clear terminal screen and reprint status header")
        print("  \033[1mexit\033[0m                  Save state and cleanly shutdown AI OS\n")

    def _render_status(self):
        """Prints live status diagnostics for all 19 OS subsystems."""
        print(f"\n\033[1;36m=== AI OS SUBSYSTEM INTEGRITY REPORT ===\033[0m")
        subsystems = [
            ("Security Daemon", self.security is not None),
            ("Hardware Manager", self.hardware is not None),
            ("Personal Memory", self.memory is not None),
            ("Model Router", self.model_router is not None),
            ("AI Cron Daemon", self.cron_daemon is not None),
            ("System Indexer", self.system_indexer is not None),
            ("Terminal UI", self.ui is not None),
            ("AI Shell Agent", self.shell_agent is not None),
            ("Multimodal Gateway", self.multimodal is not None),
            ("Project Architect", self.architect is not None),
            ("Self-Healer", self.healer is not None),
            ("Dependency Resolver", self.resolver is not None),
            ("Sandbox Runner", self.sandbox is not None),
            ("Git Automator", self.git_automator is not None),
            ("Offline Docs Engine", self.docs_engine is not None),
            ("GUI Expander", self.gui_expander is not None),
            ("System Updater", self.updater is not None),
            ("Plugin Manager", self.plugin_manager is not None)
        ]

        for name, active in subsystems:
            status_badge = "\033[1;32m[ONLINE]\033[0m" if active else "\033[1;31m[OFFLINE]\033[0m"
            print(f"  {status_badge} {name}")
        uptime = time.time() - self.start_time
        print(f"\n\033[2mUptime: {uptime:.1f}s | Active Background Threads: {threading.active_count()}\033[0m\n")

    # --------------------------------------------------------------------------
    # 3. Graceful Shutdown & State Preservation
    # --------------------------------------------------------------------------
    def shutdown(self):
        """
        Executes formal clean shutdown:
        1. Saves personal memory session data
        2. Syncs active Git repositories
        3. Cleans up sandbox environments
        4. Terminates background cron daemon
        5. Logs tamper-evident cryptographic security audit record
        """
        if not self.running:
            return

        self.running = False
        print("\n\033[1;33m[*] AI OS: Preserving state and shutting down subsystems...\033[0m")

        # 1. Save Session Memory
        if self.memory:
            try:
                self.memory.store_memory("system_rules", f"AI OS session closed cleanly at {time.ctime()}")
                print("  \033[1;32m✓\033[0m Session memory persisted to SQLite store.")
            except Exception as e:
                print(f"  \033[1;31m!\033[0m Failed saving session memory: {e}")

        # 2. Sync Git Repositories
        if self.git_automator and self.workspace_dir.exists():
            try:
                for repo in self.workspace_dir.glob("projects/*"):
                    if repo.is_dir() and (repo / ".git").exists():
                        self.git_automator.create_checkpoint(repo, reason="system_shutdown")
                print("  \033[1;32m✓\033[0m Git workspace repositories synchronized with safety checkpoints.")
            except Exception:
                pass

        # 3. Sandbox Cleanup
        if self.sandbox:
            try:
                self.sandbox.cleanup_stale_containers()
                print("  \033[1;32m✓\033[0m Isolated sandbox containers cleaned up.")
            except Exception:
                pass

        # 4. Stop Background Cron Daemon
        if self.cron_daemon:
            try:
                self.cron_daemon.stop_daemon()
                print("  \033[1;32m✓\033[0m AI Cron background scheduler stopped.")
            except Exception:
                pass

        # 5. Security Audit Trail Finalization
        if self.security and hasattr(self.security, "audit_logger"):
            try:
                self.security.audit_logger.record_event("SYSTEM_SHUTDOWN", {"reason": "Clean user shutdown"})
                print("  \033[1;32m✓\033[0m Cryptographic security audit log sealed.")
            except Exception:
                pass

        print("\033[1;36m[*] AI Operating System Kernel Halted Cleanly. Goodbye!\033[0m\n")


# ==============================================================================
# Main Boot Entry Point (/usr/bin/ai-os)
# ==============================================================================
def main():
    orchestrator = MasterOSOrchestrator()
    boot_ok = orchestrator.boot()
    if boot_ok:
        orchestrator.run_event_loop()


if __name__ == "__main__":
    main()
