#!/usr/bin/env bash
set -e

echo "======================================"
echo "  LocalAST Setup & Installation"
echo "  (Python 3.11+ version)"
echo "======================================"
echo ""

# Try to find Python 3.11+
PYTHON_CMD=""

for cmd in python3.13 python3.12 python3.11 python3; do
    if command -v $cmd &> /dev/null; then
        version=$($cmd --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
        major=$(echo $version | cut -d. -f1)
        minor=$(echo $version | cut -d. -f2)
        
        if [ "$major" -eq 3 ] && [ "$minor" -ge 11 ]; then
            PYTHON_CMD=$cmd
            echo "✓ Found $cmd (Python $version)"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "❌ Error: Python 3.11+ not found"
    echo ""
    echo "Please install Python 3.11+ first:"
    echo ""
    echo "  macOS (Homebrew):"
    echo "    brew install python@3.11"
    echo ""
    echo "  macOS (Official):"
    echo "    Download from https://www.python.org/downloads/"
    echo ""
    echo "  Conda:"
    echo "    conda create -n localast python=3.11"
    echo "    conda activate localast"
    echo ""
    exit 1
fi

echo "Using: $PYTHON_CMD"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ -d ".venv" ]; then
    echo "  Virtual environment already exists"
else
    $PYTHON_CMD -m venv .venv
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
echo "1. Keep this terminal open and run:"
echo "   localast repo add . --name localast"
echo "   localast index repo localast --embed"
echo ""
echo "2. Start the MCP server:"
echo "   localast serve"
echo ""
echo "Virtual environment is already activated!"
echo ""




