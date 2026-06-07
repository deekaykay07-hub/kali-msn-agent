#!/usr/bin/env python3
"""
msn_ui.py - Retro Windows Live / MSN Messenger 2000s style UI.
Dedicated single contact: "Jarvis" the Kali Agent.
Full OS control toggle + live tool output in classic chat windows.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import threading
import queue
import time
import os
from datetime import datetime
from pathlib import Path

from agent_core import KaliAgent, OLLAMA_HOST, MODEL_NAME

# Classic MSN-ish colors (approximations of the era)
MSN_PURPLE = "#6B2D7B"
MSN_DARK = "#1E1E2E"
MSN_TITLE_BG = "#000080"      # navy title bars
MSN_ACCENT = "#00A2E8"        # bright blue
MSN_GREEN = "#00AA00"
MSN_LIGHT_BG = "#F0F0F0"
MSN_WHITE = "#FFFFFF"
MSN_ORANGE = "#FF6600"
MSN_RED = "#CC0000"

class RetroTitleBar(tk.Frame):
    """Fake classic window title bar"""
    def __init__(self, parent, title, on_close=None, **kw):
        super().__init__(parent, bg=MSN_TITLE_BG, height=22, **kw)
        self.pack(fill=tk.X, side=tk.TOP)
        self.title_label = tk.Label(self, text=title, fg="white", bg=MSN_TITLE_BG,
                                    font=("MS Sans Serif", 9, "bold"), padx=8)
        self.title_label.pack(side=tk.LEFT, fill=tk.Y)
        if on_close:
            close_btn = tk.Label(self, text="  X  ", fg="white", bg="#800000",
                                 font=("MS Sans Serif", 8, "bold"), cursor="hand2")
            close_btn.pack(side=tk.RIGHT, fill=tk.Y)
            close_btn.bind("<Button-1>", lambda e: on_close())

class MSNMainWindow(tk.Tk):
    """The main 'MSN Messenger' contact list window."""
    def __init__(self):
        super().__init__()
        self.title("Kali MSN - Agent Messenger")
        self.geometry("280x420")
        self.resizable(False, False)
        self.configure(bg=MSN_LIGHT_BG)

        # State
        self.agent = KaliAgent(output_callback=self._agent_output)
        self.chat_window = None
        self.full_control_var = tk.BooleanVar(value=False)
        self.log_lines = []  # for export

        self._build_ui()
        self._post_init()

    def _build_ui(self):
        # Fake MSN top banner
        banner = tk.Frame(self, bg=MSN_PURPLE, height=48)
        banner.pack(fill=tk.X)
        tk.Label(banner, text="Kali MSN Agent", fg="white", bg=MSN_PURPLE,
                 font=("MS Sans Serif", 14, "bold")).pack(pady=6)
        tk.Label(banner, text="Windows Live Messenger style • Full Root Access",
                 fg="#FFCCFF", bg=MSN_PURPLE, font=("MS Sans Serif", 7)).pack()

        # Menu simulation
        menubar = tk.Frame(self, bg="#E0E0E0", height=20)
        menubar.pack(fill=tk.X)
        for label, cmd in [("File", self._menu_file), ("Contacts", self._menu_contacts),
                           ("Actions", self._menu_actions), ("Help", self._menu_help)]:
            b = tk.Label(menubar, text=label, bg="#E0E0E0", padx=8, font=("MS Sans Serif", 8))
            b.pack(side=tk.LEFT)
            b.bind("<Button-1>", lambda e, c=cmd: c())

        # Status area
        status_frame = tk.Frame(self, bg=MSN_LIGHT_BG, pady=4)
        status_frame.pack(fill=tk.X, padx=6)
        tk.Label(status_frame, text="Status:", font=("MS Sans Serif", 8)).pack(side=tk.LEFT)
        self.status_label = tk.Label(status_frame, text="● Online", fg=MSN_GREEN,
                                     font=("MS Sans Serif", 8, "bold"))
        self.status_label.pack(side=tk.LEFT, padx=4)
        tk.Label(status_frame, text=f"  Model: {MODEL_NAME}", fg="#555",
                 font=("MS Sans Serif", 7)).pack(side=tk.RIGHT)

        # Contact list header
        tk.Label(self, text="Online (1)", bg="#D0D0D0", anchor="w",
                 font=("MS Sans Serif", 8, "bold"), padx=4).pack(fill=tk.X, padx=4, pady=(6,0))

        # The single dedicated contact - "Jarvis"
        contact = tk.Frame(self, bg=MSN_WHITE, bd=1, relief=tk.RIDGE)
        contact.pack(fill=tk.X, padx=6, pady=2)
        contact.bind("<Double-Button-1>", lambda e: self._open_chat())

        avatar = tk.Label(contact, text="☠", font=("Segoe UI Symbol", 18),
                          bg=MSN_WHITE, width=3, fg="#222")
        avatar.pack(side=tk.LEFT, padx=4, pady=2)

        info = tk.Frame(contact, bg=MSN_WHITE)
        info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(info, text="Jarvis", bg=MSN_WHITE, fg=MSN_DARK,
                 font=("MS Sans Serif", 10, "bold"), anchor="w").pack(fill=tk.X)
        tk.Label(info, text="Kali Agent • Full OS Control", bg=MSN_WHITE, fg=MSN_ACCENT,
                 font=("MS Sans Serif", 7), anchor="w").pack(fill=tk.X)
        tk.Label(info, text="Online - Ready for ops", bg=MSN_WHITE, fg=MSN_GREEN,
                 font=("MS Sans Serif", 7), anchor="w").pack(fill=tk.X)

        contact.bind("<Enter>", lambda e: contact.config(bg="#E8F4FF"))
        contact.bind("<Leave>", lambda e: contact.config(bg=MSN_WHITE))

        # Full Control toggle (the big red button of power)
        ctrl = tk.Frame(self, bg=MSN_LIGHT_BG, pady=8)
        ctrl.pack(fill=tk.X, padx=6)
        self.ctrl_check = tk.Checkbutton(
            ctrl,
            text="ENABLE FULL CONTROL (root shell access)",
            variable=self.full_control_var,
            command=self._toggle_full_control,
            bg=MSN_LIGHT_BG, fg=MSN_RED, font=("MS Sans Serif", 8, "bold"),
            selectcolor="#FFCCCC"
        )
        self.ctrl_check.pack(anchor="w")
        tk.Label(ctrl, text="⚠ All commands the agent decides to run will execute immediately.",
                 fg="#880000", bg=MSN_LIGHT_BG, font=("MS Sans Serif", 6)).pack(anchor="w")

        # Quick action buttons (old school)
        quick = tk.Frame(self, bg=MSN_LIGHT_BG)
        quick.pack(fill=tk.X, padx=6, pady=4)
        for txt, prompt in [
            ("Quick Recon", "Perform a quick local network recon and show me live hosts and interfaces."),
            ("WiFi Scan", "Put wifi in monitor mode if needed and run a 25s airodump to discover nearby APs. Show results."),
            ("Plan & Execute", "Ask me for a goal (e.g. 'capture WPA handshake on BSSID XX and crack it') then create a numbered plan and execute it step by step using tools."),
        ]:
            b = tk.Button(quick, text=txt, font=("MS Sans Serif", 7),
                          command=lambda p=prompt: self._quick_action(p))
            b.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

        # Bottom status / version
        tk.Label(self, text=f"Ollama @ {OLLAMA_HOST}   •   {datetime.now().strftime('%Y-%m-%d')}",
                 bg="#E8E8E8", fg="#666", font=("MS Sans Serif", 6)).pack(fill=tk.X, side=tk.BOTTOM)

    def _post_init(self):
        self.agent.full_control_enabled = False
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._emit_system("Kali MSN Agent ready. Double-click Jarvis to open chat.")
        self._emit_system("Toggle FULL CONTROL above before asking for dangerous ops (aircrack, etc).")

    def _toggle_full_control(self):
        enabled = self.full_control_var.get()
        self.agent.full_control_enabled = enabled
        if enabled:
            self.status_label.config(text="● FULL CONTROL", fg=MSN_RED)
            self._emit_system("!!! FULL OS CONTROL ENABLED - agent can run ANY command !!!")
        else:
            self.status_label.config(text="● Online", fg=MSN_GREEN)
            self._emit_system("Full control disabled. Risky commands will be blocked.")

    def _agent_output(self, tag: str, text: str):
        """Called from agent_core (and its worker threads) to push text into UI."""
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {text}"
        self.log_lines.append((tag, line))

        # If chat window is open, forward to it (thread-safe via after)
        if self.chat_window and self.chat_window.winfo_exists():
            self.chat_window.after(0, lambda: self.chat_window.append_output(tag, text))

    def _emit_system(self, text: str):
        self._agent_output("system", text)

    def _open_chat(self):
        if self.chat_window and self.chat_window.winfo_exists():
            self.chat_window.lift()
            return
        self.chat_window = ChatWindow(self, self.agent, on_close=self._chat_closed)
        self.chat_window.title("Conversation - Jarvis")
        self._emit_system("Chat opened with Jarvis (the Agent).")

    def _chat_closed(self):
        self.chat_window = None

    def _quick_action(self, prompt: str):
        self._open_chat()
        # Give the window a moment to appear then send
        self.after(120, lambda: self.chat_window.send_user_message(prompt))

    # --- Fake menus ---
    def _menu_file(self):
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Export Chat Log...", command=self._export_log)
        m.add_separator()
        m.add_command(label="Reset Conversation", command=self._reset_conv)
        m.add_command(label="Exit", command=self._on_close)
        m.tk_popup(self.winfo_pointerx(), self.winfo_pointery())

    def _menu_contacts(self):
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Add Contact (disabled - single agent mode)", state="disabled")
        m.add_command(label="Show Jarvis Properties", command=lambda: messagebox.showinfo(
            "Jarvis", "Jarvis - Kali Linux Agent\nModel: jarvis:latest\nFull remote shell + tool calling enabled."))
        m.tk_popup(self.winfo_pointerx(), self.winfo_pointery())

    def _menu_actions(self):
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Open Real Terminal", command=self._spawn_terminal)
        m.add_command(label="Run: iwconfig", command=lambda: self._inject_shell("iwconfig"))
        m.add_command(label="Run: ip addr", command=lambda: self._inject_shell("ip -c addr"))
        m.add_command(label="Run: airmon-ng check kill", command=lambda: self._inject_shell("sudo airmon-ng check kill"))
        m.add_separator()
        m.add_command(label="Clear all logs", command=lambda: (setattr(self, 'log_lines', []), self._emit_system("Logs cleared.")))
        m.tk_popup(self.winfo_pointerx(), self.winfo_pointery())

    def _menu_help(self):
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="About Kali MSN Agent", command=lambda: messagebox.showinfo(
            "Kali MSN Agent",
            "Retro MSN Messenger skin over a powerful Kali Linux agent.\n\n"
            "• Talks to jarvis:latest on 165.22.112.6:11434 (standard Ollama port)\n"
            "• Full shell execution + multi-step plan execution (aircrack workflows etc.)\n"
            "• Built for Kali Live persistent USB auto-start\n\n"
            "WARNING: This grants the AI unrestricted access to your OS."))
        m.add_command(label="How to use on USB (D:)", command=self._show_usb_help)
        m.tk_popup(self.winfo_pointerx(), self.winfo_pointery())

    def _spawn_terminal(self):
        for term in ["xterm", "gnome-terminal", "konsole"]:
            try:
                if term == "gnome-terminal":
                    os.system(f"{term} -- bash -l &")
                else:
                    os.system(f"{term} -e bash -l &")
                self._emit_system(f"Spawned {term}")
                return
            except Exception:
                pass
        self._emit_system("No terminal emulator found. Try: xterm or gnome-terminal")

    def _inject_shell(self, cmd: str):
        self._open_chat()
        self.after(80, lambda: self.chat_window.send_direct_shell(cmd))

    def _reset_conv(self):
        if self.agent:
            self.agent.reset_conversation()
        self._emit_system("Conversation history reset.")

    def _export_log(self):
        if not self.log_lines:
            messagebox.showinfo("Export", "Nothing to export yet.")
            return
        path = f"/tmp/kali_msn_log_{int(time.time())}.txt"
        try:
            with open(path, "w") as f:
                for tag, line in self.log_lines:
                    f.write(f"[{tag}] {line}\n")
            self._emit_system(f"Log exported to {path}")
            messagebox.showinfo("Exported", f"Saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _show_usb_help(self):
        messagebox.showinfo(
            "USB Instructions (D:)",
            "See the included startup/ folder and README.\n\n"
            "Typical steps:\n"
            "1. On Windows copy the whole kali-msn-agent folder to D:\\kali-msn-agent\n"
            "2. Boot your Kali Live USB (persistent)\n"
            "3. Run the persist-setup.sh once from the persistent home\n"
            "4. Or copy files into ~/.config/autostart\n\n"
            "Full details in README.md and startup/boot-instructions.txt"
        )

    def _on_close(self):
        if messagebox.askokcancel("Exit", "Close Kali MSN Agent?"):
            try:
                if self.chat_window:
                    self.chat_window.destroy()
            except Exception:
                pass
            self.destroy()


class ChatWindow(tk.Toplevel):
    """Classic separate MSN chat window for the Jarvis contact."""
    def __init__(self, master, agent: KaliAgent, on_close=None):
        super().__init__(master)
        self.agent = agent
        self.on_close = on_close
        self.geometry("520x420")
        self.configure(bg=MSN_LIGHT_BG)
        self.resizable(True, True)

        self._build_chat_ui()
        self.protocol("WM_DELETE_WINDOW", self._handle_close)

        # Queue + polling for thread-safe output from agent
        self.ui_queue = queue.Queue()
        self.after(80, self._poll_queue)

    def _build_chat_ui(self):
        # Title bar
        RetroTitleBar(self, "Jarvis - Kali Agent (Online)", on_close=self._handle_close)

        # Header strip (contact info)
        header = tk.Frame(self, bg="#E8F0F8", height=28)
        header.pack(fill=tk.X)
        tk.Label(header, text="To: Jarvis   [Agent - Full Access]", bg="#E8F0F8",
                 fg=MSN_DARK, font=("MS Sans Serif", 9, "bold"), padx=6).pack(side=tk.LEFT)
        self.typing_label = tk.Label(header, text="", bg="#E8F0F8", fg=MSN_ACCENT,
                                     font=("MS Sans Serif", 7, "italic"))
        self.typing_label.pack(side=tk.RIGHT, padx=8)

        # Chat history (the most important retro part)
        self.history = scrolledtext.ScrolledText(
            self, wrap=tk.WORD, height=16, state="disabled",
            font=("Courier New", 9), bg=MSN_WHITE, fg="#111111",
            relief=tk.SUNKEN, bd=1
        )
        self.history.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        # Tag styling for retro feel
        self.history.tag_config("user", foreground="#0000AA", font=("Courier New", 9, "bold"))
        self.history.tag_config("agent", foreground="#006600")
        self.history.tag_config("system", foreground="#884400", font=("Courier New", 8, "italic"))
        self.history.tag_config("command", foreground=MSN_ORANGE, font=("Courier New", 9, "bold"))
        self.history.tag_config("output", foreground="#222222", font=("Courier New", 8))
        self.history.tag_config("tool", foreground="#660066", font=("Courier New", 8))

        # Bottom toolbar
        toolbar = tk.Frame(self, bg=MSN_LIGHT_BG)
        toolbar.pack(fill=tk.X, padx=4, pady=2)

        tk.Button(toolbar, text="Nudge", font=("MS Sans Serif", 7),
                  command=lambda: self.append_output("system", "* You nudged Jarvis *")).pack(side=tk.LEFT, padx=1)
        tk.Button(toolbar, text="Spawn Terminal", font=("MS Sans Serif", 7),
                  command=self._spawn_term).pack(side=tk.LEFT, padx=1)
        tk.Button(toolbar, text="Direct Shell...", font=("MS Sans Serif", 7),
                  command=self._ask_direct_shell).pack(side=tk.LEFT, padx=1)
        tk.Button(toolbar, text="Stop Jobs", font=("MS Sans Serif", 7),
                  command=self._stop_jobs).pack(side=tk.LEFT, padx=1)

        # Input area (classic)
        input_frame = tk.Frame(self, bg=MSN_LIGHT_BG)
        input_frame.pack(fill=tk.X, padx=4, pady=4)

        self.input_var = tk.StringVar()
        self.input_entry = tk.Entry(input_frame, textvariable=self.input_var,
                                    font=("MS Sans Serif", 9), relief=tk.SUNKEN)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2)
        self.input_entry.bind("<Return>", lambda e: self._send())
        self.input_entry.focus_set()

        send_btn = tk.Button(input_frame, text="Send", width=8, command=self._send,
                             bg=MSN_ACCENT, fg="white", font=("MS Sans Serif", 8, "bold"))
        send_btn.pack(side=tk.RIGHT, padx=2)

        # Hint line
        tk.Label(self, text="Type normally or start with /shell for raw commands. Agent uses tools automatically.",
                 bg=MSN_LIGHT_BG, fg="#666", font=("MS Sans Serif", 6)).pack(fill=tk.X)

    def append_output(self, tag: str, text: str):
        """Append a message to the chat log (safe to call from any thread via .after)."""
        self.history.config(state="normal")
        prefix = {"user": "You: ", "agent": "Jarvis: ", "system": "[*] ",
                  "command": "$ ", "output": "   ", "tool": "[tool] "}.get(tag, "")
        self.history.insert(tk.END, prefix + text + "\n", tag)
        self.history.see(tk.END)
        self.history.config(state="disabled")

    def _set_typing(self, text: str = ""):
        self.typing_label.config(text=text)

    def _send(self):
        text = self.input_var.get().strip()
        if not text:
            return
        self.input_var.set("")
        self.append_output("user", text)

        if text.startswith("/shell ") or text.startswith("!"):
            cmd = text.split(" ", 1)[1] if " " in text else ""
            self.send_direct_shell(cmd)
            return

        # Normal LLM path
        self._set_typing("Jarvis is thinking...")
        threading.Thread(target=self._worker_send, args=(text,), daemon=True).start()

    def send_user_message(self, text: str):
        """Public helper used by quick actions."""
        self.append_output("user", text)
        self._set_typing("Jarvis is thinking...")
        threading.Thread(target=self._worker_send, args=(text,), daemon=True).start()

    def send_direct_shell(self, cmd: str):
        if not cmd:
            return
        self.append_output("system", f"Direct shell: {cmd}")
        threading.Thread(target=self._worker_direct, args=(cmd,), daemon=True).start()

    def _worker_send(self, text: str):
        try:
            self.agent.send_message(text, enable_tools=True)
        finally:
            self.after(0, lambda: self._set_typing(""))

    def _worker_direct(self, cmd: str):
        try:
            out = self.agent.direct_shell(cmd, timeout=35)
            if out:
                self.after(0, lambda: self.append_output("output", out[-4000:]))
        except Exception as e:
            self.after(0, lambda: self.append_output("system", f"Direct error: {e}"))

    def _poll_queue(self):
        try:
            while True:
                tag, text = self.ui_queue.get_nowait()
                self.append_output(tag, text)
        except queue.Empty:
            pass
        self.after(120, self._poll_queue)

    def _spawn_term(self):
        self.append_output("system", "Spawning visible terminal...")
        for t in ["xterm", "gnome-terminal", "konsole", "xfce4-terminal"]:
            if os.system(f"which {t} >/dev/null 2>&1") == 0:
                os.system(f"{t} -e 'bash -l' &")
                self.append_output("system", f"Opened {t}")
                return
        self.append_output("system", "No graphical terminal found.")

    def _ask_direct_shell(self):
        cmd = simpledialog.askstring("Direct Shell", "Command to run directly (bypasses agent):",
                                     parent=self)
        if cmd:
            self.send_direct_shell(cmd)

    def _stop_jobs(self):
        self.append_output("system", "Asking agent to stop background jobs (if tracked)...")
        threading.Thread(target=lambda: self.agent.execute_shell(
            "sudo pkill -f airodump; sudo pkill -f airmon; sudo pkill -f hcxdumptool; echo 'killed monitors if any'", timeout=8
        ), daemon=True).start()

    def _handle_close(self):
        if self.on_close:
            self.on_close()
        self.destroy()
