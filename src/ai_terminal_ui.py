#!/usr/bin/env python3
"""
ai_terminal_ui.py - Rich Terminal TTY UI & Interactive AI Dashboard
Author: CLI UI/UX Engineer and Terminal Graphics Specialist

Provides a modern, visually stunning, readable, and responsive interface for AI OS
in default TTY / CLI mode using `rich` with ANSI fallbacks.
Features:
- Streaming Markdown with real-time Syntax Highlighting
- Live Activity Spinners & Progress Trackers
- Interactive Command Autocompletion & Tab-Completion
- System Status Header & Live Resource Footer (CPU/RAM/Model/Network)
- Keybindings (Ctrl+C, Ctrl+L, Ctrl+G to toggle GUI)
"""

import os
import sys
import time
import shutil
import platform
import threading
from contextlib import contextmanager
from typing import Dict, List, Optional, Any, Generator, Tuple

# Try loading rich
try:
    if sys.platform == "win32":
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            if hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.panel import Panel
    from rich.table import Table
    from rich.live import Live
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich.layout import Layout
    from rich.text import Text
    from rich.theme import Theme
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# Try loading prompt_toolkit for interactive terminal prompt
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.completion import Completer, Completion, PathCompleter, WordCompleter
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.formatted_text import ANSI
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False

# Try loading psutil for system metrics
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# ==============================================================================
# Theme & Color Definitions
# ==============================================================================
CUSTOM_THEME = Theme({
    "info": "bold cyan",
    "warning": "bold yellow",
    "danger": "bold red",
    "success": "bold green",
    "accent": "bold magenta",
    "muted": "dim white",
    "header": "bold white on blue",
    "status": "bold white on dark_blue"
}) if HAS_RICH else None


# ==============================================================================
# Terminal UI Engine
# ==============================================================================
class AITerminalUI:
    """
    Main interface controller for TTY rendering, markdown parsing, syntax highlighting,
    live indicators, status banners, and interactive prompts.
    """

    def __init__(self, force_terminal: bool = True):
        self.has_rich = HAS_RICH
        if self.has_rich:
            self.console = Console(theme=CUSTOM_THEME, force_terminal=force_terminal)
        else:
            self.console = None
        self.default_model = "llama3.2:3b"
        self._active_spinner = None

    # --------------------------------------------------------------------------
    # System Status & Header / Footer
    # --------------------------------------------------------------------------
    def get_system_metrics(self) -> Dict[str, Any]:
        """Collects live system CPU, RAM, and disk utilization."""
        metrics = {
            "cpu_percent": 0.0,
            "ram_percent": 0.0,
            "ram_used_mb": 0,
            "ram_total_mb": 0,
            "online": False
        }

        if HAS_PSUTIL:
            try:
                metrics["cpu_percent"] = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory()
                metrics["ram_percent"] = ram.percent
                metrics["ram_used_mb"] = int(ram.used / (1024 * 1024))
                metrics["ram_total_mb"] = int(ram.total / (1024 * 1024))
            except Exception:
                pass
        else:
            # Fallback for minimal Linux /proc inspection
            try:
                if os.path.exists("/proc/meminfo"):
                    with open("/proc/meminfo", "r") as f:
                        lines = f.readlines()
                    total = 0
                    free = 0
                    for line in lines:
                        if "MemTotal:" in line:
                            total = int(line.split()[1]) // 1024
                        elif "MemAvailable:" in line or "MemFree:" in line:
                            free = int(line.split()[1]) // 1024
                    if total > 0:
                        metrics["ram_total_mb"] = total
                        metrics["ram_used_mb"] = total - free
                        metrics["ram_percent"] = round(((total - free) / total) * 100, 1)
            except Exception:
                pass

        # Check network connectivity (ping or socket check)
        metrics["online"] = self._check_connectivity()
        return metrics

    def _check_connectivity(self) -> bool:
        """Lightweight non-blocking socket test to check internet connection."""
        import socket
        try:
            s = socket.create_connection(("1.1.1.1", 53), timeout=0.8)
            s.close()
            return True
        except Exception:
            return False

    def render_header(self, model: Optional[str] = None, cwd: Optional[str] = None):
        """Displays a clean top status header."""
        model_name = model or self.default_model
        curr_cwd = cwd or os.getcwd()
        metrics = self.get_system_metrics()
        status_badge = "[bold green]ONLINE[/bold green]" if metrics["online"] else "[bold yellow]OFFLINE (Local Only)[/bold yellow]"

        if self.has_rich:
            header_table = Table.grid(expand=True)
            header_table.add_column(justify="left", ratio=2)
            header_table.add_column(justify="center", ratio=2)
            header_table.add_column(justify="right", ratio=2)

            header_table.add_row(
                f"[bold cyan]AI OS[/bold cyan] [dim]| Kernel TTY[/dim]",
                f"[bold magenta]Model:[/bold magenta] {model_name} [dim]| Status:[/dim] {status_badge}",
                f"[dim]Dir:[/dim] [bold yellow]{curr_cwd}[/bold yellow]"
            )
            panel = Panel(header_table, style="blue", border_style="cyan", padding=(0, 1))
            self.console.print(panel)
        else:
            net_status = "ONLINE" if metrics["online"] else "OFFLINE"
            print(f"\033[1;36m[AI OS TTY]\033[0m Model: \033[1;35m{model_name}\033[0m | Dir: \033[1;33m{curr_cwd}\033[0m | Net: \033[1;32m{net_status}\033[0m")
            print("\033[2m" + "-" * 78 + "\033[0m")

    def render_status_bar(self, model: Optional[str] = None, cwd: Optional[str] = None):
        """Displays bottom status bar showing RAM/CPU load and active directory."""
        model_name = model or self.default_model
        curr_cwd = cwd or os.getcwd()
        metrics = self.get_system_metrics()

        if self.has_rich:
            status_text = (
                f"[bold cyan]Model:[/bold cyan] {model_name}  |  "
                f"[bold magenta]CPU:[/bold magenta] {metrics['cpu_percent']}%  |  "
                f"[bold yellow]RAM:[/bold yellow] {metrics['ram_used_mb']}/{metrics['ram_total_mb']} MB ({metrics['ram_percent']}%)  |  "
                f"[bold green]CWD:[/bold green] {curr_cwd}  |  "
                f"Status: {'[bold green]Connected[/bold green]' if metrics['online'] else '[dim]Local[/dim]'}"
            )
            self.console.print(Panel(status_text, style="dim white on grey15", border_style="dim grey42", padding=(0, 1)))
        else:
            print(f"\033[7m Model: {model_name} | CPU: {metrics['cpu_percent']}% | RAM: {metrics['ram_percent']}% | CWD: {curr_cwd} \033[0m")

    # --------------------------------------------------------------------------
    # Streaming Markdown & Syntax Highlighting
    # --------------------------------------------------------------------------
    def render_markdown(self, markdown_text: str):
        """Renders complete markdown text with tables, headers, and code syntax highlighting."""
        if self.has_rich:
            md = Markdown(markdown_text, code_theme="monokai", inline_code_lexer="python")
            self.console.print(md)
        else:
            # Fallback ANSI rendering
            self._render_ansi_markdown(markdown_text)

    def stream_markdown(self, token_generator: Generator[str, None, None]):
        """
        Streams AI output tokens in real-time, progressively updating markdown rendering
        with live syntax highlighting.
        """
        full_text = ""
        if self.has_rich:
            with Live(console=self.console, refresh_per_second=12, auto_refresh=True) as live:
                for token in token_generator:
                    full_text += token
                    live.update(Markdown(full_text, code_theme="monokai"))
        else:
            for token in token_generator:
                sys.stdout.write(token)
                sys.stdout.flush()
            sys.stdout.write("\n")
        return full_text

    def render_code_block(self, code: str, language: str = "python", title: Optional[str] = None):
        """Renders syntax-highlighted code block in a structured panel."""
        if self.has_rich:
            syntax = Syntax(code, language, theme="monokai", line_numbers=True, word_wrap=True)
            panel = Panel(syntax, title=title or f"Code [{language}]", border_style="cyan")
            self.console.print(panel)
        else:
            print(f"\n--- {title or language.upper()} ---")
            print(code)
            print("-" * 40 + "\n")

    def render_table(self, title: str, headers: List[str], rows: List[List[str]]):
        """Renders clean styled tabular data."""
        if self.has_rich:
            table = Table(title=title, border_style="cyan", header_style="bold magenta")
            for h in headers:
                table.add_column(h, style="white")
            for r in rows:
                table.add_row(*r)
            self.console.print(table)
        else:
            print(f"\n=== {title} ===")
            print(" | ".join(headers))
            print("-" * (len(" | ".join(headers)) + 4))
            for r in rows:
                print(" | ".join(r))
            print()

    def render_badge(self, text: str, badge_type: str = "INFO"):
        """Displays status badge: [READY], [ERROR], [WARN], [ACTIVE]."""
        color_map = {
            "INFO": ("bold cyan", "\033[1;36m"),
            "SUCCESS": ("bold green", "\033[1;32m"),
            "WARNING": ("bold yellow", "\033[1;33m"),
            "ERROR": ("bold red", "\033[1;31m"),
            "ACTIVE": ("bold magenta", "\033[1;35m")
        }
        rich_style, ansi_code = color_map.get(badge_type.upper(), ("bold white", "\033[1m"))

        if self.has_rich:
            self.console.print(f"[{rich_style}]\\[{badge_type.upper()}][/{rich_style}] {text}")
        else:
            print(f"{ansi_code}[{badge_type.upper()}]\033[0m {text}")

    # --------------------------------------------------------------------------
    # Real-Time Activity Spinners & Progress Bars
    # --------------------------------------------------------------------------
    @contextmanager
    def activity_spinner(self, description: str, success_msg: Optional[str] = None, fail_msg: Optional[str] = None):
        """
        Displays an animated status spinner for background actions.
        Example: [✓] Generating code... | [⟳] Installing dependencies...
        """
        if self.has_rich:
            spinner_type = "simpleDotsAscii" if sys.platform == "win32" else "dots"
            try:
                progress = Progress(
                    SpinnerColumn(spinner_name=spinner_type),
                    TextColumn("[bold cyan]{task.description}"),
                    TimeElapsedColumn(),
                    console=self.console,
                    transient=True
                )
                task_id = progress.add_task(description=description, total=None)
                progress.start()
                started_rich = True
            except Exception:
                progress = None
                started_rich = False

            if started_rich and progress:
                try:
                    yield progress
                    progress.stop()
                    if success_msg:
                        self.console.print(f"[bold green]\\[✓][/bold green] {success_msg}")
                except Exception as e:
                    progress.stop()
                    if fail_msg:
                        self.console.print(f"[bold red]\\[✗][/bold red] {fail_msg}: {e}")
                    else:
                        self.console.print(f"[bold red]\\[✗][/bold red] Failed {description}: {e}")
                    raise
                return

        # Fallback ANSI or Plain Output
        print(f"\033[1;36m[⟳] {description}...\033[0m", end="", flush=True)
        try:
            yield None
            print(f"\r\033[1;32m[✓] {success_msg or description + ' done'}\033[0m")
        except Exception as e:
            print(f"\r\033[1;31m[✗] {fail_msg or description + ' failed'}: {e}\033[0m")
            raise

    def create_progress_bar(self, total: int, description: str) -> Any:
        """Creates an animated progress bar for downloads, builds, or test suites."""
        if self.has_rich:
            progress = Progress(
                TextColumn("[bold cyan]{task.description}"),
                BarColumn(complete_style="cyan", finished_style="green"),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=self.console
            )
            task_id = progress.add_task(description=description, total=total)
            return progress, task_id
        return None, None

    # --------------------------------------------------------------------------
    # Interactive Command Autocompletion, History & Keybindings
    # --------------------------------------------------------------------------
    def create_interactive_session(self, history_file: Optional[str] = None, commands: Optional[List[str]] = None) -> Any:
        """
        Initializes prompt_toolkit session with autocompletion, tab-completion for paths,
        arrow-key history, and custom keybindings (Ctrl+C, Ctrl+L, Ctrl+G).
        """
        if not HAS_PROMPT_TOOLKIT:
            return None

        h_path = history_file or os.path.expanduser("~/.ai_shell_history")
        hist = FileHistory(h_path)

        builtins = commands or [
            "ask", "models", "pull", "status", "heal", "build", "sandbox",
            "security", "memory", "help", "clear", "exit", "gui", "voice", "vision"
        ]

        # Combine word autocompletion with filesystem path autocompletion
        class CombinedCompleter(Completer):
            def __init__(self, words: List[str]):
                self.word_completer = WordCompleter(words, ignore_case=True, sentence=False)
                self.path_completer = PathCompleter(expanduser=True)

            def get_completions(self, document, complete_event):
                text_before = document.text_before_cursor
                tokens = text_before.strip().split()

                # If first word, offer command completions
                if len(tokens) <= 1 and not text_before.endswith(" "):
                    for c in self.word_completer.get_completions(document, complete_event):
                        yield c
                else:
                    # Provide path completions for arguments
                    for c in self.path_completer.get_completions(document, complete_event):
                        yield c

        kb = KeyBindings()

        # Keybinding: Ctrl+L to clear screen & reprint header
        @kb.add("c-l")
        def _clear_screen(event):
            event.app.renderer.clear()
            self.render_header()

        # Keybinding: Ctrl+G to toggle GUI mode
        @kb.add("c-g")
        def _toggle_gui(event):
            self.render_badge("Toggling GUI mode...", "INFO")
            toggle_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "toggle_gui.sh"))
            if os.path.exists(toggle_script):
                import subprocess
                subprocess.Popen(["sh", toggle_script])
            else:
                self.render_badge("toggle_gui.sh not found", "WARNING")

        session = PromptSession(
            history=hist,
            completer=CombinedCompleter(builtins),
            auto_suggest=AutoSuggestFromHistory(),
            key_bindings=kb,
            enable_history_search=True
        )
        return session

    def prompt(self, session: Any, prompt_str: str = "ai-os > ") -> str:
        """Prompts user with full autocomplete and keyboard navigation."""
        if session and HAS_PROMPT_TOOLKIT:
            try:
                return session.prompt(ANSI(prompt_str)).strip()
            except (KeyboardInterrupt, EOFError):
                raise
        else:
            try:
                return input(prompt_str).strip()
            except (KeyboardInterrupt, EOFError):
                raise

    # --------------------------------------------------------------------------
    # Fallback Plain ANSI Markdown Parser
    # --------------------------------------------------------------------------
    def _render_ansi_markdown(self, text: str):
        in_code_block = False
        for line in text.splitlines():
            if line.startswith("```"):
                in_code_block = not in_code_block
                print("\033[2m" + "-" * 40 + "\033[0m")
                continue
            if in_code_block:
                print(f"\033[32m{line}\033[0m")
            elif line.startswith("# "):
                print(f"\033[1;36m{line}\033[0m")
            elif line.startswith("## "):
                print(f"\033[1;34m{line}\033[0m")
            elif line.startswith("- ") or line.startswith("* "):
                print(f"  \033[1;33m•\033[0m {line[2:]}")
            else:
                print(line)


# ==============================================================================
# Stdout Stream Wrapper (Integration with ai_shell_agent.py)
# ==============================================================================
class AIStreamStdoutWrapper:
    """
    Wraps standard sys.stdout to intercept streaming LLM tokens, buffering and
    formatting markdown live on terminal output.
    """

    def __init__(self, ui: AITerminalUI):
        self.ui = ui
        self.original_stdout = sys.stdout
        self.buffer = []

    def write(self, s: str):
        if not s:
            return
        self.buffer.append(s)
        self.original_stdout.write(s)
        self.original_stdout.flush()

    def flush(self):
        self.original_stdout.flush()

    def get_buffered_content(self) -> str:
        return "".join(self.buffer)

    def clear(self):
        self.buffer.clear()


# ==============================================================================
# CLI Testing & Demonstration Entrypoint
# ==============================================================================
def main():
    ui = AITerminalUI()

    print("\n--- Testing Header ---")
    ui.render_header(model="llama3.2:3b", cwd="/workspace")

    print("\n--- Testing Streaming Markdown ---")
    sample_tokens = [
        "# AI OS Security Report\n\n",
        "The system has been evaluated with the following findings:\n\n",
        "- **Status**: Operating at normal capacity\n",
        "- **Active Guardrails**: Enforced via `security_daemon.py`\n\n",
        "```python\n",
        "def check_security():\n",
        "    return {'safe': True, 'score': 100}\n",
        "```\n\n",
        "| Subsystem | State | Risk |\n",
        "|---|---|---|\n",
        "| Sandboxing | Active | Low |\n",
        "| Rollback | Armed | Zero |\n"
    ]
    ui.stream_markdown(iter(sample_tokens))

    print("\n--- Testing Activity Spinner ---")
    with ui.activity_spinner("Synthesizing system profile", success_msg="Profile verified"):
        time.sleep(0.5)

    print("\n--- Testing Status Bar ---")
    ui.render_status_bar(model="llama3.2:3b", cwd="/workspace")
    print()


if __name__ == "__main__":
    main()
