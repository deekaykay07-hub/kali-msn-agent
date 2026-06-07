# Kali MSN Agent

**Retro MSN Messenger (2000s Windows Live style) chat interface to a powerful Kali Linux AI agent.**

- Single dedicated contact: **Jarvis** (the agent)
- Talks to the **jarvis:latest** model running on your droplet at `http://165.22.112.6:11434` (standard Ollama port)
- Full OS control: the agent can execute **any** shell command, run `aircrack-ng` suites, capture handshakes, recon networks, write scripts, spawn terminals, etc.
- Multi-step autonomous planning: ask it to "capture the WPA2 handshake on this network and crack it" — it will create a plan and use tools to drive the entire workflow.
- Designed for **Kali Live USB with persistence** — includes everything you need to make it autostart from the boot menu / desktop session.

## Quick Start (on your Kali box)

```bash
cd /path/to/kali-msn-agent
sudo apt update
sudo apt install -y python3-tk python3-requests xterm   # xterm recommended for spawn_terminal
python3 main.py
```

1. In the main MSN window, **check the red "ENABLE FULL CONTROL"** box (otherwise dangerous commands are blocked).
2. Double-click **Jarvis** to open the chat.
3. Type natural language goals. Examples:
   - "Show me all network interfaces and do a quick ARP scan of the LAN"
   - "Put the wifi card in monitor mode and run a 30 second airodump to find APs"
   - "Help me capture a WPA handshake on BSSID XX:XX:XX:XX:XX:XX channel 6 and then crack it with rockyou"
   - "Write a small python script that scans for hosts and saves it to /tmp/scan.py then run it"

The agent will use tool-calling to drive `execute_shell`, read files, spawn visible xterms for live airodump, etc. You will see every command and its output appear in the chat log in real time.

## Configuration

- Default remote: `http://165.22.112.6:11434` + model `jarvis:latest`
- Override at runtime:
  ```bash
  OLLAMA_HOST=http://165.22.112.6:11434 \
  OLLAMA_MODEL=jarvis:latest \
  python3 main.py
  ```

The model on the droplet already has an excellent Kali pentesting system prompt (the Modelfile you had). The UI adds the tool definitions on top so the model can actually *act*.

## USB Persistent Kali Live Setup (your D: drive)

Your USB when plugged into Windows shows the live partition as **D:**.

### Recommended workflow

1. **On Windows** (while USB is plugged in):
   - Copy the entire `kali-msn-agent` folder to `D:\kali-msn-agent`
   - Also copy (or create) the files from the `startup/` folder to the root of D: if you want a one-click launcher visible in the file browser.

2. **Boot your Kali Live USB** (choose the persistent option from the boot menu).

3. Once on the desktop, open a terminal and run the one-time setup:

   ```bash
   cd /media/kali/XXXX-XXXX/kali-msn-agent   # or wherever the FAT32 partition is mounted
   # OR if you copied it into the persistent home already:
   cd ~/kali-msn-agent
   chmod +x startup/persist-setup.sh
   ./startup/persist-setup.sh
   ```

   This script will:
   - Copy the agent into `~/kali-msn-agent` (persisted)
   - Create `~/.config/autostart/kali-msn-agent.desktop` so it starts when the desktop loads
   - Make sure python3-tk + requests are installed
   - Optionally add a small "Kali MSN" entry that appears in menus

4. Reboot the live USB (or log out/in). The MSN window should appear automatically.

### "Clicked from the boot menu" option

If you want a dedicated boot menu entry that boots straight into a mode that launches the agent (more advanced):

- You would normally remaster the ISO or use the persistence + a custom `live` config, but the easiest practical thing is:
  - Use the autostart desktop file (above).
  - Or press the "Kali" menu → "System" (or just run the desktop file) after boot.

For a true custom boot entry you would edit the `isolinux`/`grub` config on the USB and add a label that runs a custom init, but that is outside the scope of a simple "add files to USB". The autostart + `persist-setup.sh` is what 95% of people want.

See [startup/boot-instructions.txt](startup/boot-instructions.txt) for the exact file placement on D: and the manual steps.

## Safety & Responsibility

- This tool gives the LLM **unrestricted root-level shell access** to the machine it runs on.
- Only use it on dedicated pentest hardware / live USBs.
- The model prompt already asks for authorization confirmation on real attacks — respect the law.
- All executed commands are logged to the chat and can be exported.

## Project Structure

```
kali-msn-agent/
├── main.py              # Entry point
├── agent_core.py        # Ollama client + full tool calling + shell execution engine
├── msn_ui.py            # The entire retro MSN Messenger UI (main window + chat window)
├── requirements.txt
├── README.md
├── startup/
│   ├── persist-setup.sh
│   ├── kali-msn-agent.desktop
│   └── boot-instructions.txt
└── assets/              # (future icons etc.)
```

## GitHub

https://github.com/deekaykay07-hub/kali-msn-agent

## Serving / Downloading

When the author ran the build, the directory was served on a local port so you can grab the files directly onto your USB (D:).

## Credits

Built for your exact request: old-school MSN aesthetic + the jarvis model on the droplet + complete Kali control + USB persistence story.

Have fun (and stay legal).
