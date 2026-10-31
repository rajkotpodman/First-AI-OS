#!/usr/bin/env python3
"""
ai-os-shell: Core TTY CLI Shell for AI Operating System
Bootstrapped on Alpine Linux TTY1
"""
import os
import sys
import subprocess
import shutil
import time

BANNER = r"""
   _____   ____       ____   _____ 
  /  _  \ |    |     /  _ \ /  ___/
 /  /_\  \|    |    /  <_\ \\___ \ 
/    |    \    |___ \_____//____  >
\____|__  /_______ \      /_____  / 
        \/        \/            \/  
 [ AI Operating System - Minimal TTY Kernel Runtime ]
"""

class AIOSShell:
    def __init__(self):
        self.hostname = "ai-os"
        self.user = os.getenv("USER", "root")
        self.history = []
        self.workspace = "/workspace"
        os.chdir(self.workspace if os.path.exists(self.workspace) else "/root")

    def print_banner(self):
        print("\033[1;36m" + BANNER + "\033[0m")
        print("\033[1;32m[*] Kernel Boot Complete.\033[0m")
        print("\033[1;33m[*] Services: OpenRC [ACTIVE] | Docker [READY] | AI-Agent [ACTIVE]\033[0m")
        print("\033[1;34m[*] Mounts: /home, /workspace, /var/lib/docker (OverlayFS Active)\033[0m")
        print("\033[0;37mType 'help' for built-in AI OS commands, 'ask <prompt>' for local LLM, or run standard shell commands.\033[0m\n")

    def run_sys_cmd(self, cmd_str):
        try:
            subprocess.run(cmd_str, shell=True)
        except Exception as e:
            print(f"\033[1;31mError executing command: {e}\033[0m")

    def check_ollama_status(self):
        try:
            res = subprocess.run(["curl", "-s", "http://127.0.0.1:11434/api/tags"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0:
                return True
        except Exception:
            pass
        return False

    def query_local_llm(self, prompt):
        if not self.check_ollama_status():
            print("\033[1;33m[!] Local LLM daemon (Ollama) is initializing or not responding at :11434.\033[0m")
            print("    Check service status with: 'rc-service ai-agent status'")
            return

        print("\033[1;35m[AI Agent Thinking...]\033[0m")
        try:
            # Using curl to query Ollama directly or fallback to ollama cli
            cmd = [
                "curl", "-s", "-X", "POST", "http://127.0.0.1:11434/api/generate",
                "-d", f'{{"model": "llama3.2:1b", "prompt": "{prompt}", "stream": false}}'
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if res.returncode == 0 and "response" in res.stdout:
                import json
                data = json.loads(res.stdout)
                print(f"\033[1;32m[AI Agent]:\033[0m {data.get('response', '').strip()}\n")
            else:
                # Direct CLI fallback
                subprocess.run(f"ollama run llama3.2:1b \"{prompt}\"", shell=True)
        except Exception as e:
            print(f"\033[1;31mLLM query failed: {e}\033[0m")

    def handle_builtin(self, cmd):
        tokens = cmd.strip().split()
        if not tokens:
            return True
        action = tokens[0].lower()

        if action in ("exit", "logout"):
            print("\033[1;33mExiting AI OS Shell... Respawning session.\033[0m")
            time.sleep(1)
            return False
        elif action == "help":
            print("""\033[1;37m
AI OS Builtin Commands:
  ask <prompt>       - Direct prompt to the locally running LLM model
  models             - List pulled local AI models
  pull <model>       - Download a model into local persistent storage
  status             - Inspect AI agent, Docker, and persistence storage
  sh / bash          - Drop into native Unix subshell
  reboot / poweroff  - Clean system power management
\033[0m""")
            return True
        elif action == "ask":
            prompt = " ".join(tokens[1:])
            if not prompt:
                print("Usage: ask <your question or instructions>")
            else:
                self.query_local_llm(prompt)
            return True
        elif action == "models":
            self.run_sys_cmd("ollama list")
            return True
        elif action == "pull":
            if len(tokens) > 1:
                self.run_sys_cmd(f"ollama pull {tokens[1]}")
            else:
                print("Usage: pull <model_name> (e.g. pull llama3.2:1b)")
            return True
        elif action == "status":
            print("\n--- System Memory & Storage ---")
            self.run_sys_cmd("free -h")
            print("\n--- Disk Layout & Overlays ---")
            self.run_sys_cmd("df -h / /home /workspace /var/lib/docker 2>/dev/null || df -h")
            print("\n--- Services Status ---")
            self.run_sys_cmd("rc-status default")
            print()
            return True
        else:
            # Fallback to standard system commands
            self.run_sys_cmd(cmd)
            return True

    def loop(self):
        self.print_banner()
        while True:
            try:
                cwd = os.getcwd()
                prompt_str = f"\033[1;36mai-os\033[0m:\033[1;34m{cwd}\033[0m\033[1;32m ⚡ \033[0m"
                cmd = input(prompt_str)
                if not self.handle_builtin(cmd):
                    break
            except (KeyboardInterrupt, EOFError):
                print()
                continue
            except Exception as e:
                print(f"\033[1;31mUnexpected shell error: {e}\033[0m")

if __name__ == "__main__":
    shell = AIOSShell()
    shell.loop()
