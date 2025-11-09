#!/usr/bin/env bash
set -e

echo "================================================"
echo "  LocalAST Complete Installation"
echo "  (Installs Python 3.11+ if needed)"
echo "================================================"
echo ""

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "⚠️  This script is for macOS. For other OS, please install Python 3.11+ manually."
    echo ""
    echo "Then run: ./setup-python311.sh"
    exit 1
fi

# Check if Homebrew is installed
echo "Checking for Homebrew..."
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew not found. Installing Homebrew first..."
    echo ""
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for Apple Silicon Macs
    if [[ $(uname -m) == 'arm64' ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
    
    echo "✓ Homebrew installed"
else
    echo "✓ Homebrew found"
fi
echo ""

# Check for Python 3.11+
echo "Checking for Python 3.11+..."
PYTHON_FOUND=false

for cmd in python3.13 python3.12 python3.11; do
    if command -v $cmd &> /dev/null; then
        version=$($cmd --version 2>&1 | awk '{print $2}')
        echo "✓ Found $cmd (version $version)"
        PYTHON_FOUND=true
        break
    fi
done

if [ "$PYTHON_FOUND" = false ]; then
    echo "❌ Python 3.11+ not found. Installing via Homebrew..."
    echo ""
    brew install python@3.11
    echo ""
    echo "✓ Python 3.11 installed"
    
    # Add to PATH
    echo 'export PATH="/usr/local/opt/python@3.11/bin:$PATH"' >> ~/.zshrc
    export PATH="/usr/local/opt/python@3.11/bin:$PATH"
else
    echo "✓ Python 3.11+ already installed"
fi
echo ""

# Now run the setup
echo "Running LocalAST setup..."
echo ""
./setup-python311.sh

# Check if setup was successful
if [ $? -eq 0 ]; then
    echo ""
    echo "================================================"
    echo "  ✓ Complete Installation Successful!"
    echo "================================================"
    echo ""
    echo "To start using LocalAST:"
    echo ""
    echo "1. Activate the virtual environment (if not already):"
    echo "   source .venv/bin/activate"
    echo ""
    echo "2. Register and index this repository:"
    echo "   localast repo add . --name localast"
    echo "   localast index repo localast --embed"
    echo ""
    echo "3. Check results:"
    echo "   localast repo info"
    echo ""
    echo "4. Start MCP server:"
    echo "   localast serve"
    echo ""
else
    echo ""
    echo "❌ Setup failed. Please check the errors above."
    exit 1
fi




