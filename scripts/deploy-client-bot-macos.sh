#!/bin/bash

# MeatLizard Client Bot Deployment Script for macOS with Apple Silicon
# This script sets up the AI inference client bot on macOS

set -e

echo "🦎 MeatLizard Client Bot - macOS Deployment"
echo "==========================================="

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ This script is designed for macOS only"
    exit 1
fi

# Check for Apple Silicon
if [[ $(uname -m) != "arm64" ]]; then
    echo "⚠️  This script is optimized for Apple Silicon (M1/M2/M3)"
    echo "   It may work on Intel Macs but performance will be limited"
    read -p "Continue anyway? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if client bot config exists
if [ ! -f "client_bot/config.yml" ]; then
    echo "❌ client_bot/config.yml not found. Creating from template..."
    
    # Create config directory
    mkdir -p client_bot/config
    
    # Create config file
    cat > client_bot/config.yml << EOF
client_bot:
  token: "${DISCORD_CLIENT_BOT_TOKEN}"
  server_bot_id: "${DISCORD_SERVER_BOT_ID}"

payload_encryption_key: "${PAYLOAD_ENCRYPTION_KEY}"

llama_cpp:
  executable_path: "/usr/local/bin/llama-cpp"
  n_ctx: 4096
  threads: 6
  n_gpu_layers: 28

models:
  - alias: "default"
    path: "/path/to/your/model.gguf"
    description: "Default 7B model"
  - alias: "large"
    path: "/path/to/your/large-model.gguf"
    description: "Larger 13B model"

monitoring:
  enable_battery_monitor: true
  low_battery_threshold_percent: 20
  metrics_reporting_interval: 30
EOF
    
    echo "✅ Created client_bot/config.yml template"
    echo "⚠️  Please edit client_bot/config.yml with your actual values before continuing"
    exit 1
fi

# Install Homebrew if not present
if ! command -v brew &> /dev/null; then
    echo "🍺 Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    echo "✅ Homebrew installed"
fi

# Install system dependencies
echo "📦 Installing system dependencies..."
brew update
brew install python@3.11 cmake pkg-config git wget

# Install llama.cpp with Metal support
echo "🔧 Installing llama.cpp with Metal support..."
if [ ! -d "llama.cpp" ]; then
    git clone https://github.com/ggerganov/llama.cpp.git
fi

cd llama.cpp
git pull
make clean
LLAMA_METAL=1 make -j$(sysctl -n hw.ncpu)

# Install to system path
sudo cp main /usr/local/bin/llama-cpp
sudo chmod +x /usr/local/bin/llama-cpp

cd ..
echo "✅ llama.cpp installed with Metal support"

# Create Python virtual environment
echo "🐍 Setting up Python environment..."
cd client_bot

if [ ! -d "venv" ]; then
    python3.11 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip

# Install Python dependencies
pip install -r requirements.txt

# Install additional dependencies for production
pip install psutil pyyaml cryptography

echo "✅ Python environment configured"

# Download a default model if none exists
echo "🤖 Checking for language models..."
models_dir="$HOME/llama-models"
mkdir -p "$models_dir"

if [ ! -f "$models_dir/llama-2-7b-chat.Q5_K_M.gguf" ]; then
    echo "📥 Downloading default model (this may take a while)..."
    cd "$models_dir"
    wget -c "https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/resolve/main/llama-2-7b-chat.Q5_K_M.gguf"
    cd - > /dev/null
    
    # Update config with model path
    sed -i '' "s|/path/to/your/model.gguf|$models_dir/llama-2-7b-chat.Q5_K_M.gguf|g" config.yml
    echo "✅ Default model downloaded and configured"
else
    echo "✅ Model already exists"
fi

# Create launch script
echo "📝 Creating launch script..."
cat > run_client_bot.sh << 'EOF'
#!/bin/bash

# MeatLizard Client Bot Launch Script
cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Check battery level
battery_level=$(pmset -g batt | grep -Eo "\d+%" | cut -d% -f1)
if [ "$battery_level" -lt 20 ]; then
    echo "⚠️  Low battery ($battery_level%). Consider plugging in for optimal performance."
fi

# Check if plugged in
if pmset -g batt | grep -q "AC Power"; then
    echo "🔌 Running on AC power - optimal performance mode"
else
    echo "🔋 Running on battery - performance may be limited"
fi

# Start the client bot
echo "🚀 Starting MeatLizard Client Bot..."
python client_bot_production.py
EOF

chmod +x run_client_bot.sh
echo "✅ Launch script created"

# Create launchd plist for auto-start
echo "🔄 Setting up auto-start service..."
plist_path="$HOME/Library/LaunchAgents/com.meatlizard.clientbot.plist"

cat > "$plist_path" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.meatlizard.clientbot</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(pwd)/run_client_bot.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$(pwd)</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$(pwd)/logs/client_bot.log</string>
    <key>StandardErrorPath</key>
    <string>$(pwd)/logs/client_bot_error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF

# Load the service
launchctl unload "$plist_path" 2>/dev/null || true
launchctl load "$plist_path"

echo "✅ Auto-start service configured"

# Create monitoring script
echo "📊 Creating monitoring script..."
cat > monitor_client_bot.sh << 'EOF'
#!/bin/bash

# MeatLizard Client Bot Monitoring Script

echo "🦎 MeatLizard Client Bot Status"
echo "=============================="

# Check if service is running
if launchctl list | grep -q "com.meatlizard.clientbot"; then
    echo "✅ Service is loaded"
else
    echo "❌ Service is not loaded"
fi

# Check process
if pgrep -f "client_bot_production.py" > /dev/null; then
    echo "✅ Client bot is running"
    
    # Get process info
    pid=$(pgrep -f "client_bot_production.py")
    echo "   PID: $pid"
    
    # Memory usage
    memory=$(ps -o rss= -p $pid | awk '{print $1/1024 " MB"}')
    echo "   Memory: $memory"
    
    # CPU usage
    cpu=$(ps -o %cpu= -p $pid)
    echo "   CPU: $cpu%"
else
    echo "❌ Client bot is not running"
fi

# System info
echo ""
echo "💻 System Information:"
echo "   Model: $(system_profiler SPHardwareDataType | grep "Model Name" | cut -d: -f2 | xargs)"
echo "   Chip: $(system_profiler SPHardwareDataType | grep "Chip" | cut -d: -f2 | xargs)"
echo "   Memory: $(system_profiler SPHardwareDataType | grep "Memory" | cut -d: -f2 | xargs)"

# Battery info
battery_info=$(pmset -g batt)
if echo "$battery_info" | grep -q "InternalBattery"; then
    battery_level=$(echo "$battery_info" | grep -Eo "\d+%" | cut -d% -f1)
    power_source=$(echo "$battery_info" | grep -q "AC Power" && echo "AC Power" || echo "Battery")
    echo "   Battery: $battery_level% ($power_source)"
fi

# GPU info
echo "   GPU: $(system_profiler SPDisplaysDataType | grep "Chipset Model" | cut -d: -f2 | xargs | head -1)"

# Recent logs
echo ""
echo "📋 Recent Logs (last 10 lines):"
if [ -f "logs/client_bot.log" ]; then
    tail -10 logs/client_bot.log
else
    echo "   No logs found"
fi
EOF

chmod +x monitor_client_bot.sh
echo "✅ Monitoring script created"

# Create logs directory
mkdir -p logs

# Test the configuration
echo "🧪 Testing configuration..."
if python client_bot_production.py --test 2>/dev/null; then
    echo "✅ Configuration test passed"
else
    echo "⚠️  Configuration test failed - please check your config.yml"
fi

cd ..

echo ""
echo "🎉 MeatLizard Client Bot deployed successfully!"
echo "============================================="
echo ""
echo "📍 Installation Location: $(pwd)/client_bot"
echo "🔧 Configuration File: $(pwd)/client_bot/config.yml"
echo "🚀 Launch Script: $(pwd)/client_bot/run_client_bot.sh"
echo "📊 Monitor Script: $(pwd)/client_bot/monitor_client_bot.sh"
echo ""
echo "📝 Next Steps:"
echo "1. Edit client_bot/config.yml with your Discord bot token and server details"
echo "2. Download or configure your language models"
echo "3. Test the bot: cd client_bot && ./run_client_bot.sh"
echo "4. Monitor status: cd client_bot && ./monitor_client_bot.sh"
echo ""
echo "🔧 Service Management:"
echo "  - Start: launchctl load ~/Library/LaunchAgents/com.meatlizard.clientbot.plist"
echo "  - Stop: launchctl unload ~/Library/LaunchAgents/com.meatlizard.clientbot.plist"
echo "  - Restart: launchctl unload ~/Library/LaunchAgents/com.meatlizard.clientbot.plist && launchctl load ~/Library/LaunchAgents/com.meatlizard.clientbot.plist"
echo ""
echo "📚 Performance Tips:"
echo "  - Keep your Mac plugged in for optimal performance"
echo "  - Use Q5_K_M or Q4_K_M quantized models for best speed/quality balance"
echo "  - Monitor temperature and throttling with Activity Monitor"
echo "  - Consider using smaller models (7B) for real-time chat"
echo ""
echo "🎊 Client bot deployment completed!"