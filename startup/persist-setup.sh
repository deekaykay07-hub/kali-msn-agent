#!/bin/bash
#
# persist-setup.sh
# One-time setup script to make Kali MSN Agent autostart on a persistent Kali Live USB.
#
# Run this AFTER booting into your persistent Kali Live session.
# It will copy the agent into your home (which persists) and create an autostart .desktop entry.
#

set -e

AGENT_SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="$HOME/kali-msn-agent"
AUTOSTART_DIR="$HOME/.config/autostart"

echo "=== Kali MSN Agent - Persistent USB Setup ==="
echo "Source : $AGENT_SRC_DIR"
echo "Target : $TARGET_DIR"

# 1. Make sure we have the runtime deps
echo "[1/5] Installing runtime packages (python3-tk, python3-requests, xterm)..."
sudo apt-get update -qq || true
sudo apt-get install -y -qq python3-tk python3-requests xterm gnome-terminal konsole 2>/dev/null || \
sudo apt-get install -y -qq python3-tk python3-requests xterm

# 2. Copy (or rsync) the whole agent tree into the persistent home
echo "[2/5] Copying agent files into persistent home..."
mkdir -p "$TARGET_DIR"
rsync -a --delete --exclude '.git' --exclude '__pycache__' "$AGENT_SRC_DIR/" "$TARGET_DIR/" 2>/dev/null || \
cp -a "$AGENT_SRC_DIR"/* "$TARGET_DIR/" 2>/dev/null || true
cp -a "$AGENT_SRC_DIR"/.[!.]* "$TARGET_DIR/" 2>/dev/null || true   # dotfiles if any

chmod +x "$TARGET_DIR"/*.py "$TARGET_DIR"/startup/*.sh 2>/dev/null || true

# 3. Create autostart entry so it launches when desktop session starts
echo "[3/5] Creating autostart .desktop entry..."
mkdir -p "$AUTOSTART_DIR"

cat > "$AUTOSTART_DIR/kali-msn-agent.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Name=Kali MSN Agent
Comment=Retro MSN Messenger interface to the Jarvis Kali agent (full OS control)
Exec=/usr/bin/python3 /home/kali/kali-msn-agent/main.py
Icon=utilities-terminal
Terminal=false
Categories=Network;Security;
X-GNOME-Autostart-enabled=true
StartupNotify=false
EOF

chmod +x "$AUTOSTART_DIR/kali-msn-agent.desktop"

# 4. Also drop a launcher on the Desktop for manual start (common on live)
echo "[4/5] Creating Desktop launcher..."
mkdir -p "$HOME/Desktop"
cat > "$HOME/Desktop/Kali-MSN-Agent.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Name=Kali MSN Agent
Comment=Old-school MSN chat to full-control Kali agent
Exec=/usr/bin/python3 /home/kali/kali-msn-agent/main.py
Icon=utilities-terminal
Terminal=false
Categories=Network;Security;
EOF
chmod +x "$HOME/Desktop/Kali-MSN-Agent.desktop"

# 5. Optional: add a small note in the live user's .bashrc so they see how to start it from tty too
if ! grep -q "kali-msn-agent" "$HOME/.bashrc" 2>/dev/null; then
cat >> "$HOME/.bashrc" << 'EOF'

# Kali MSN Agent helper
alias kali-msn='python3 ~/kali-msn-agent/main.py'
echo "Type 'kali-msn' to launch the retro agent messenger."
EOF
fi

echo "[5/5] Done."
echo
echo "Next steps:"
echo "  • Log out and back in, or reboot the live USB (with persistence enabled)."
echo "  • The MSN window should appear automatically on desktop load."
echo "  • If it doesn't pop, click the icon on the Desktop or run:"
echo "      python3 ~/kali-msn-agent/main.py"
echo
echo "Remember: check the red 'ENABLE FULL CONTROL' box in the main window before"
echo "asking the agent to do serious work (aircrack-ng, mass scans, etc)."
echo
echo "Your USB Windows-visible partition is usually mounted under /media/kali/..."
echo "You originally placed the files on D: from Windows."
echo
echo "Setup complete. Have fun and stay legal."
