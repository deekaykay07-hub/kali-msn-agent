#!/usr/bin/env python3
"""
agent_core.py - Full control Kali agent backend.
Talks to remote Ollama (jarvis:latest) with tool calling.
Provides execute_shell and other OS control primitives.
"""

import os
import sys
import json
import time
import shlex
import signal
import subprocess
import threading
import queue
from datetime import datetime
from typing import Callable, Dict, Any, List, Optional

import requests

# === CONFIG - Standard Ollama port ===
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://165.22.112.6:11434")
MODEL_NAME = os.environ.get("OLLAMA_MODEL", "jarvis:latest")
API_TIMEOUT = 120  # seconds for the overall chat call
SHELL_DEFAULT_TIMEOUT = 45
MAX_OUTPUT_CHARS = 16000  # truncate huge outputs

# Dangerous command patterns (still allowed because user wants full control, but we log + prefix in chat)
DANGEROUS_PREFIXES = (
    "rm -rf /",
    "dd if=",
    "mkfs",
    ":(){ :|:& };: ",
    "shutdown",
    "reboot",
    "poweroff",
    "halt",
)

def is_dangerous(cmd: str) -> bool:
    c = cmd.strip().lower()
    return any(c.startswith(p) for p in DANGEROUS_PREFIXES) or (" / " in c and "rm -rf" in c)

class KaliAgent:
    def __init__(self, output_callback: Optional[Callable[[str, str], None]] = None):
        self.output_callback = output_callback or (lambda tag, text: print(f"[{tag.upper()}] {text}"))
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.conversation: List[Dict[str, Any]] = []
        self._current_jobs: Dict[str, subprocess.Popen] = {}
        self.full_control_enabled = False  # toggled from UI

    def _emit(self, tag: str, text: str):
        try:
            self.output_callback(tag, text)
        except Exception:
            pass

    def reset_conversation(self):
        self.conversation = []

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "execute_shell",
                    "description": "Execute ANY shell command on the Kali Linux machine with full privileges. Use for nmap, aircrack-ng suite, airmon-ng, iwconfig, ifconfig, netdiscover, airodump-ng (with timeout), hcxdumptool, reaver, pixiewps, metasploit, python3 one-liners, apt, systemctl, echo to files, etc. Supports long-running via background=true or by spawning xterm/gnome-terminal. Returns combined stdout+stderr + exit code.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "The exact shell command to run (can include sudo, pipes, &&, etc)."},
                            "timeout": {"type": "integer", "description": "Max seconds to wait. Default 45. Use 120+ for slow scans."},
                            "background": {"type": "boolean", "description": "If true, launch with nohup & and return immediately (for monitors, listeners)."},
                            "spawn_terminal": {"type": "boolean", "description": "If true, try to pop an xterm/gnome-terminal/konsole with the command so user sees live output."}
                        },
                        "required": ["command"]
                    }
                }
            },
            {"type": "function", "function": {"name": "get_system_info", "description": "Get basic system info: hostname, user, interfaces, uptime, kernel, current working dir.", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "list_wifi_interfaces", "description": "List wireless interfaces and their current mode (managed/monitor). Useful before airmon-ng.", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "read_file", "description": "Read the contents of a file on disk (e.g. capture-01.cap summary via strings, logs, /etc files, scripts you wrote).", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "max_bytes": {"type": "integer"}}, "required": ["path"]}}},
            {"type": "function", "function": {"name": "write_file", "description": "Write or append text to a file. Use to create custom scripts, wordlists snippets, config files, etc.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}, "append": {"type": "boolean", "default": false}}, "required": ["path", "content"]}}},
            {"type": "function", "function": {"name": "kill_job", "description": "Kill a background job previously started by execute_shell (by pid).", "parameters": {"type": "object", "properties": {"pid": {"type": "integer"}}, "required": ["pid"]}}}
        ]

    def _run_shell(self, command: str, timeout: int = SHELL_DEFAULT_TIMEOUT, background: bool = False, spawn_terminal: bool = False) -> Dict[str, Any]:
        if spawn_terminal:
            terms = ["xterm", "gnome-terminal", "konsole", "xfce4-terminal", "lxterminal"]
            for term in terms:
                try:
                    if term == "gnome-terminal":
                        p = subprocess.Popen([term, "--", "bash", "-c", f"{command}; exec bash"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    else:
                        p = subprocess.Popen([term, "-hold", "-e", command], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return {"ok": True, "pid": p.pid, "output": f"[SPAWNED] {term} with command (live window). PID={p.pid}", "exit_code": 0, "background": True}
                except FileNotFoundError:
                    continue
            background = True

        if background:
            try:
                full = f"nohup {command} > /tmp/kali_msn_bg_{int(time.time())}.log 2>&1 & echo $!"
                out = subprocess.check_output(["bash", "-c", full], timeout=5, text=True).strip()
                pid = int(out.split()[-1]) if out else -1
                return {"ok": True, "pid": pid, "output": f"[BACKGROUND] Launched: {command}\nPID: {pid}", "exit_code": 0, "background": True}
            except Exception as e:
                return {"ok": False, "output": f"Background launch failed: {e}", "exit_code": 1}

        start = time.time()
        try:
            proc = subprocess.Popen(["bash", "-c", command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, preexec_fn=os.setsid)
            output_lines = []
            try:
                for line in iter(proc.stdout.readline, ""):
                    if not line: break
                    output_lines.append(line.rstrip("\n"))
                    self._emit("output", line.rstrip("\n"))
                    if len("\n".join(output_lines)) > MAX_OUTPUT_CHARS:
                        output_lines.append("... [OUTPUT TRUNCATED] ...")
                        break
                    if (time.time() - start) > timeout: break
            finally:
                try: proc.stdout.close()
                except: pass
            remaining = max(1, timeout - int(time.time() - start))
            try:
                exit_code = proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                try: proc.wait(timeout=2)
                except: os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                exit_code = -9
                output_lines.append(f"\n[TIMEOUT after {timeout}s - process terminated]")
            full_output = "\n".join(output_lines)
            if len(full_output) > MAX_OUTPUT_CHARS:
                full_output = full_output[:MAX_OUTPUT_CHARS] + "\n... [TRUNCATED]"
            return {"ok": exit_code == 0, "pid": proc.pid, "output": full_output, "exit_code": exit_code, "runtime": round(time.time() - start, 1)}
        except Exception as e:
            return {"ok": False, "output": f"Execution error: {str(e)}", "exit_code": 127}

    def execute_shell(self, command: str, timeout: int = SHELL_DEFAULT_TIMEOUT, background: bool = False, spawn_terminal: bool = False) -> Dict[str, Any]:
        cmd = command.strip()
        self._emit("command", f"$ {cmd}")
        if is_dangerous(cmd) and not self.full_control_enabled:
            msg = "BLOCKED dangerous command (enable Full Control in the MSN window first)."
            self._emit("system", msg)
            return {"ok": False, "output": msg, "exit_code": 126}
        result = self._run_shell(cmd, timeout=timeout, background=background, spawn_terminal=spawn_terminal)
        status = "OK" if result.get("ok") else "FAIL"
        summary = f"[{status} exit={result.get('exit_code')}] runtime={result.get('runtime', '?')}s"
        if result.get("pid"): summary += f" pid={result['pid']}"
        self._emit("system", summary)
        return result

    def get_system_info(self) -> Dict[str, Any]:
        info = {}
        try:
            info["hostname"] = os.uname().nodename
            info["user"] = os.environ.get("USER", "kali")
            info["cwd"] = os.getcwd()
            info["kernel"] = os.uname().release
            try:
                out = subprocess.check_output(["ip", "-brief", "addr"], text=True, timeout=4)
                info["interfaces"] = out.strip().splitlines()
            except Exception:
                info["interfaces"] = ["(ip command failed)"]
            info["uptime"] = subprocess.check_output(["uptime"], text=True, timeout=3).strip()
        except Exception as e: info["error"] = str(e)
        self._emit("tool", json.dumps(info, indent=2)[:2000])
        return info

    def list_wifi_interfaces(self) -> Dict[str, Any]:
        try:
            out = subprocess.check_output(["iwconfig"], text=True, timeout=6, stderr=subprocess.STDOUT)
        except Exception as e: out = str(getattr(e, 'output', e))
        self._emit("tool", "iwconfig:\n" + out[:3000])
        return {"iwconfig": out}

    def read_file(self, path: str, max_bytes: int = 8192) -> Dict[str, Any]:
        try:
            with open(os.path.expanduser(path), "rb") as f: data = f.read(max_bytes)
            text = data.decode("utf-8", errors="replace")
            self._emit("tool", f"read {path} ({len(data)} bytes)")
            return {"path": path, "content": text, "truncated": len(data) == max_bytes}
        except Exception as e: return {"error": str(e)}

    def write_file(self, path: str, content: str, append: bool = False) -> Dict[str, Any]:
        try:
            mode = "a" if append else "w"
            with open(os.path.expanduser(path), mode, encoding="utf-8") as f: f.write(content)
            self._emit("tool", f"wrote {len(content)} bytes -> {path}")
            return {"ok": True, "path": path, "bytes": len(content)}
        except Exception as e: return {"ok": False, "error": str(e)}

    def kill_job(self, pid: int) -> Dict[str, Any]:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            return {"ok": True, "pid": pid, "msg": "SIGTERM sent"}
        except Exception as e: return {"ok": False, "error": str(e)}

    def _ollama_chat(self, messages: List[Dict], tools: Optional[List] = None, stream: bool = False) -> Dict:
        payload = {"model": MODEL_NAME, "messages": messages, "stream": stream, "options": {"temperature": 0.7, "top_p": 0.9, "num_ctx": 16384}}
        if tools: payload["tools"] = tools
        url = f"{OLLAMA_HOST}/api/chat"
        resp = self.session.post(url, json=payload, timeout=API_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def send_message(self, user_text: str, enable_tools: bool = True) -> str:
        self.conversation.append({"role": "user", "content": user_text})
        self._emit("user", user_text)
        final_text = ""
        max_tool_rounds = 6
        for round_num in range(max_tool_rounds):
            try:
                data = self._ollama_chat(self.conversation, tools=self.tools if enable_tools else None, stream=False)
            except requests.RequestException as e:
                err = f"[OLLAMA ERROR] {e}"
                self._emit("system", err)
                final_text = err
                break
            msg = data.get("message", {})
            assistant_content = msg.get("content", "") or ""
            tool_calls = msg.get("tool_calls", []) or []
            if assistant_content:
                self._emit("agent", assistant_content)
                final_text = assistant_content
            if tool_calls:
                self.conversation.append({"role": "assistant", "content": assistant_content, "tool_calls": tool_calls})
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    name = fn.get("name")
                    args = fn.get("arguments") or {}
                    if isinstance(args, str):
                        try: args = json.loads(args)
                        except: args = {"raw": args}
                    self._emit("tool", f"→ {name}({json.dumps(args)[:200]})")
                    result = {"error": "unknown tool"}
                    try:
                        if name == "execute_shell":
                            result = self.execute_shell(args.get("command", ""), int(args.get("timeout", SHELL_DEFAULT_TIMEOUT)), bool(args.get("background", False)), bool(args.get("spawn_terminal", False)))
                        elif name == "get_system_info": result = self.get_system_info()
                        elif name == "list_wifi_interfaces": result = self.list_wifi_interfaces()
                        elif name == "read_file": result = self.read_file(args.get("path", ""), int(args.get("max_bytes", 8192)))
                        elif name == "write_file": result = self.write_file(args.get("path", ""), args.get("content", ""), bool(args.get("append", False)))
                        elif name == "kill_job": result = self.kill_job(int(args.get("pid", 0)))
                        else: result = {"error": f"Tool {name} not implemented"}
                    except Exception as ex: result = {"error": str(ex)}
                    tool_msg = {"role": "tool", "content": json.dumps(result, ensure_ascii=False)[:12000]}
                    if "id" in tc: tool_msg["tool_call_id"] = tc["id"]
                    self.conversation.append(tool_msg)
                continue
            if assistant_content:
                self.conversation.append({"role": "assistant", "content": assistant_content})
            break
        else:
            self._emit("system", "[MAX TOOL ROUNDS REACHED]")
        return final_text or "(no response)"

    def direct_shell(self, command: str, timeout: int = 30) -> str:
        self._emit("system", "DIRECT SHELL MODE (bypassed LLM)")
        res = self.execute_shell(command, timeout=timeout)
        return res.get("output", "")
