#!/bin/bash
# Check LocalAST MCP Server Status

echo "================================================================"
echo "LocalAST MCP Server Status Check"
echo "================================================================"
echo ""

# Find all running instances
PIDS=$(pgrep -f "localast serve")

if [ -z "$PIDS" ]; then
    echo "❌ MCP Server is NOT running"
    echo ""
    echo "To start it:"
    echo "  cd /Users/viswanathsekar/localast"
    echo "  ./START_MCP_SERVER.sh"
    exit 1
fi

# Count instances
COUNT=$(echo "$PIDS" | wc -l | tr -d ' ')

echo "✅ MCP Server is RUNNING"
echo "   Instance count: $COUNT"
echo ""

if [ "$COUNT" -gt 1 ]; then
    echo "⚠️  WARNING: Multiple instances detected!"
    echo "   This may cause conflicts. Recommended: keep only 1 instance."
    echo ""
fi

echo "Running Processes:"
echo "----------------------------------------------------------------"
ps -p $(echo $PIDS | tr '\n' ',' | sed 's/,$//') -o pid,start,time,command
echo ""

# Check database
echo "----------------------------------------------------------------"
echo "Database Status:"
echo "----------------------------------------------------------------"
DB_PATH="$HOME/.localast/localast.db"

if [ -f "$DB_PATH" ]; then
    echo "✅ Database: $DB_PATH"
    
    # Get database stats
    echo ""
    sqlite3 "$DB_PATH" <<SQL
.mode column
.headers on
SELECT 
    (SELECT COUNT(*) FROM repo) as repos,
    (SELECT COUNT(*) FROM files) as files,
    (SELECT COUNT(*) FROM symbols) as symbols,
    (SELECT COUNT(*) FROM emb WHERE index_kind='code') as code_embeddings,
    (SELECT COUNT(*) FROM version) as commits;
SQL
else
    echo "❌ Database not found at $DB_PATH"
fi

echo ""
echo "================================================================"
echo "Validation Complete"
echo "================================================================"


