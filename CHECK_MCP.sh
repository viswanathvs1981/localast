#!/bin/bash

# Quick MCP Server Status Check

echo "═══════════════════════════════════════════════════════════════════"
echo "LocalAST MCP Server Status Check"
echo "═══════════════════════════════════════════════════════════════════"
echo

# 1. Check if venv exists
echo "1. Virtual Environment:"
if [ -d ".venv" ]; then
    echo "   ✅ Found at: $(pwd)/.venv"
else
    echo "   ❌ .venv not found!"
    exit 1
fi
echo

# 2. Check if localast command exists
echo "2. LocalAST Command:"
if [ -f ".venv/bin/localast" ]; then
    echo "   ✅ Found at: .venv/bin/localast"
else
    echo "   ❌ Not found! Run: pip install -e ."
    exit 1
fi
echo

# 3. Check database
echo "3. Database:"
if [ -f "$HOME/.localast/localast.db" ]; then
    SIZE=$(du -h "$HOME/.localast/localast.db" | cut -f1)
    echo "   ✅ Found at: $HOME/.localast/localast.db"
    echo "   Size: $SIZE"
else
    echo "   ❌ Database not found!"
    echo "   Run: python scripts/init_db.py"
    exit 1
fi
echo

# 4. Check Cursor MCP config
echo "4. Cursor MCP Config:"
if [ -f "$HOME/.cursor/mcp.json" ]; then
    echo "   ✅ Found at: $HOME/.cursor/mcp.json"
    echo "   Contents:"
    cat "$HOME/.cursor/mcp.json" | sed 's/^/      /'
else
    echo "   ❌ Not found at $HOME/.cursor/mcp.json"
    echo "   Create it with:"
    echo '   {"mcpServers":{"localast":{"command":"'$(pwd)'/.venv/bin/localast","args":["serve"]}}}'
fi
echo

# 5. Test server functionality
echo "5. Testing MCP Server:"
if .venv/bin/python test_mcp_protocol.py > /tmp/mcp_test.log 2>&1; then
    echo "   ✅ Server test passed!"
    TOOL_COUNT=$(grep "Registered tools:" /tmp/mcp_test.log | awk '{print $3}')
    echo "   Tools available: $TOOL_COUNT"
else
    echo "   ❌ Server test failed!"
    echo "   Check /tmp/mcp_test.log for details"
    exit 1
fi
echo

# 6. Check if Cursor processes exist
echo "6. Cursor Status:"
if pgrep -q "Cursor"; then
    echo "   ✅ Cursor is running"
    echo "   ⚠️  For MCP to work, you must:"
    echo "      1. Quit Cursor completely (⌘ + Q)"
    echo "      2. Wait 5 seconds"
    echo "      3. Reopen Cursor"
    echo "      4. Open a NEW Cursor Chat"
else
    echo "   ℹ️  Cursor is not running"
    echo "   Start it and open a new chat to use MCP"
fi
echo

echo "═══════════════════════════════════════════════════════════════════"
echo "NEXT STEPS:"
echo "═══════════════════════════════════════════════════════════════════"
echo "1. ⌘ + Q to quit Cursor (if running)"
echo "2. Reopen Cursor"
echo "3. Open NEW Cursor Chat (⌘ + L)"
echo "4. Ask: 'Find the parse_file function in localast'"
echo "5. Look for 🔧 tool badge in the response"
echo
echo "📖 Full guide: ./CURSOR_SETUP.md"
echo "═══════════════════════════════════════════════════════════════════"


