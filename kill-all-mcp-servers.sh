#!/bin/bash
# Kill all LocalAST MCP Server instances

echo "================================================================"
echo "Stopping All LocalAST MCP Servers"
echo "================================================================"
echo ""

PIDS=$(pgrep -f "localast serve")

if [ -z "$PIDS" ]; then
    echo "✅ No MCP server instances running"
    exit 0
fi

COUNT=$(echo "$PIDS" | wc -l | tr -d ' ')
echo "Found $COUNT instance(s) running:"
echo ""

ps -p $(echo $PIDS | tr '\n' ',' | sed 's/,$//') -o pid,start,command

echo ""
echo "Stopping all instances..."
echo ""

for PID in $PIDS; do
    echo "  Killing PID $PID..."
    kill -9 $PID 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "  ✅ Stopped PID $PID"
    else
        echo "  ⚠️  Could not stop PID $PID (may already be stopped)"
    fi
done

echo ""
echo "================================================================"
echo "All MCP server instances stopped"
echo "================================================================"
echo ""
echo "To start a fresh instance:"
echo "  ./START_MCP_SERVER.sh"


