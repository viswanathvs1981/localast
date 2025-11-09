#!/usr/bin/env bash
set -e

echo "================================================"
echo "  LocalAST Quick Setup & Start"
echo "================================================"
echo ""

# Find Python 3.11+
PYTHON_CMD=""
for cmd in python3.13 python3.12 python3.11 python3; do
    if command -v $cmd &> /dev/null; then
        version=$($cmd --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
        major=$(echo $version | cut -d. -f1)
        minor=$(echo $version | cut -d. -f2)
        
        if [ "$major" -eq 3 ] && [ "$minor" -ge 11 ]; then
            PYTHON_CMD=$cmd
            echo "✓ Using $cmd (Python $version)"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "❌ Python 3.11+ not found"
    exit 1
fi
echo ""

# Create virtual environment
echo "[1/7] Creating virtual environment..."
if [ ! -d ".venv" ]; then
    $PYTHON_CMD -m venv .venv
    echo "✓ Created"
else
    echo "✓ Already exists"
fi
echo ""

# Activate
echo "[2/7] Activating virtual environment..."
source .venv/bin/activate
echo "✓ Activated"
echo ""

# Upgrade pip
echo "[3/7] Upgrading pip..."
python -m pip install --upgrade pip -q
echo "✓ Done"
echo ""

# Install dependencies
echo "[4/7] Installing dependencies (may take 2-3 minutes)..."
pip install -r requirements.txt -q
echo "✓ Dependencies installed"
echo ""

# Install LocalAST
echo "[5/7] Installing LocalAST..."
pip install -e . -q
echo "✓ LocalAST installed"
echo ""

# Initialize database
echo "[6/7] Initializing database..."
if [ ! -f "$HOME/.localast/localast.db" ]; then
    python scripts/init_db.py
    echo "✓ Database created at ~/.localast/localast.db"
else
    echo "✓ Database already exists"
fi
echo ""

# Register and index this repository
echo "[7/7] Indexing LocalAST repository..."

# Check if already registered
if localast repo list 2>/dev/null | grep -q "localast"; then
    echo "  Repository already registered, reindexing..."
    localast reindex localast
else
    echo "  Registering repository..."
    localast repo add . --name localast
    echo "  Indexing (this takes 1-2 minutes)..."
    localast index repo localast --embed
fi

echo "✓ Indexing complete"
echo ""

# Show stats
echo "================================================"
echo "  ✓ Setup Complete! Repository Stats:"
echo "================================================"
localast repo info
echo ""

# Start the server
echo "================================================"
echo "  Starting MCP Server..."
echo "================================================"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""
echo "Next: Configure Cursor/VSCode with this mcp.json:"
echo ""
cat << 'EOF'
{
  "mcpServers": {
    "localast": {
      "command": "localast",
      "args": ["serve"]
    }
  }
}
EOF
echo ""
echo "Starting server in 3 seconds..."
sleep 3

localast serve




