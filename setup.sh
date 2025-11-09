#!/usr/bin/env bash
set -e

echo "======================================"
echo "  LocalAST Setup & Installation"
echo "======================================"
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then 
    echo "❌ Error: Python 3.11+ required. You have Python $python_version"
    exit 1
fi
echo "✓ Python $python_version detected"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ -d ".venv" ]; then
    echo "  Virtual environment already exists"
else
    python3 -m venv .venv
    echo "✓ Virtual environment created"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip -q
echo "✓ pip upgraded"
echo ""

# Install dependencies
echo "Installing dependencies..."
echo "  This may take a few minutes (includes ML models)..."
pip install -r requirements.txt -q
echo "✓ Dependencies installed"
echo ""

# Install LocalAST
echo "Installing LocalAST in editable mode..."
pip install -e . -q
echo "✓ LocalAST installed"
echo ""

# Initialize database
echo "Initializing database..."
if [ -f "$HOME/.localast/localast.db" ]; then
    echo "  Database already exists at ~/.localast/localast.db"
else
    python scripts/init_db.py
    echo "✓ Database initialized at ~/.localast/localast.db"
fi
echo ""

# Check installation
echo "Verifying installation..."
if command -v localast &> /dev/null; then
    echo "✓ localast command is available"
else
    echo "❌ Error: localast command not found"
    exit 1
fi
echo ""

echo "======================================"
echo "  ✓ Installation Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Activate the virtual environment:"
echo "   source .venv/bin/activate"
echo ""
echo "2. Index this repository:"
echo "   localast repo add . --name localast"
echo "   localast index repo localast --embed"
echo ""
echo "3. Start the MCP server:"
echo "   localast serve"
echo ""
echo "Or use the quick commands below to get started!"
echo ""




