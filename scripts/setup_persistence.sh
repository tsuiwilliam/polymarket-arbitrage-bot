#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Setting up Persistence for Polymarket Bot ===${NC}"

# 1. Install tmux if needed
if ! command -v tmux &> /dev/null; then
    echo "tmux could not be found. Installing..."
    if [ -f /etc/debian_version ]; then
        apt-get update && apt-get install -y tmux
    elif [ -f /etc/redhat-release ]; then
        yum install -y tmux
    else
        echo -e "${RED}Unsupported OS. Please install tmux manually.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ tmux is installed${NC}"
fi

# 2. Create the runner script (auto-restart loop)
cat << 'EOF' > run_bot_loop.sh
#!/bin/bash
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

while true; do
    echo "Starting Multi-Market Bot..."
    # Run the bot with your specific parameters
    python3 apps/run_multi.py --coins BTC,ETH,SOL,XRP --drop 0.20 --size 0.5 2>&1 | tee -a bot.log
    
    EXIT_CODE=$?
    echo "Bot crashed or stopped with code $EXIT_CODE. Restarting in 5 seconds..."
    sleep 5
done
EOF

chmod +x run_bot_loop.sh
echo -e "${GREEN}✓ Created run_bot_loop.sh (auto-restart enabled)${NC}"

# 3. Create the startup script (tmux session manager)
cat << 'EOF' > start_bot_session.sh
#!/bin/bash
SESSION_NAME="arb-bot"
cd "$(dirname "$0")"

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "Session $SESSION_NAME already exists. Attaching..."
    tmux attach-session -t "$SESSION_NAME"
else
    echo "Starting new session $SESSION_NAME..."
    # Start tmux session detached, running the loop script
    tmux new-session -d -s "$SESSION_NAME" ./run_bot_loop.sh
    echo "Bot started in background. Use 'tmux attach -t $SESSION_NAME' to view."
fi
EOF

chmod +x start_bot_session.sh
echo -e "${GREEN}✓ Created start_bot_session.sh${NC}"

# 4. Setup Cron for Reboot Persistence
CRON_CMD="@reboot $(pwd)/start_bot_session.sh"
CRON_FILE="mycron"

# Check if job already exists
if crontab -l 2>/dev/null | grep -q "start_bot_session.sh"; then
    echo -e "${GREEN}✓ Cron job already exists${NC}"
else
    crontab -l 2>/dev/null > "$CRON_FILE" || true
    echo "$CRON_CMD" >> "$CRON_FILE"
    crontab "$CRON_FILE"
    rm "$CRON_FILE"
    echo -e "${GREEN}✓ Added @reboot cron job${NC}"
fi

# 5. Add ease-of-use aliases to .bashrc
if ! grep -q "alias attach-bot" ~/.bashrc; then
    echo "alias attach-bot='tmux attach -t arb-bot'" >> ~/.bashrc
    echo "alias stop-bot='tmux kill-session -t arb-bot'" >> ~/.bashrc
    echo -e "${GREEN}✓ Added aliases: attach-bot, stop-bot${NC}"
    echo "Run 'source ~/.bashrc' to load them."
else
     echo -e "${GREEN}✓ Aliases already present${NC}"
fi

echo -e "${GREEN}=== Setup Complete! ===${NC}"
echo "To start now: ./start_bot_session.sh"
echo "To view UI:   tmux attach -t arb-bot (or attach-bot)"
