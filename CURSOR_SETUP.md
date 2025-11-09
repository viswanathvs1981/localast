# Cursor MCP Setup Guide

## ✅ Your MCP Server Status

**31 Tools Available:**
1. search_code - Full-text search for symbols
2. search_semantic - Semantic/vector search 
3. search_documentation - Search docs
4. find_references - Find symbol references
5. get_symbol_info - Symbol details
6. get_file_context - Get file contents
7. get_documentation - Get docs for code
8. list_symbols_in_file - List file symbols
9. get_symbol_definition - Get code definition
10. get_changes_between_commits - Git diffs
...and 21 more!

**Server tested and working!** ✅

---

## 🎯 How to Use with Cursor

### Step 1: Verify MCP Config

Your config at `~/.cursor/mcp.json` should be:

```json
{
  "mcpServers": {
    "localast": {
      "command": "/Users/viswanathsekar/localast/.venv/bin/localast",
      "args": ["serve"],
      "env": {}
    }
  }
}
```

### Step 2: Completely Restart Cursor

**IMPORTANT:** This is not just closing the window!

1. Press `⌘ + Q` (or Menu > Quit Cursor)
2. Wait 5 seconds
3. Reopen Cursor
4. Wait for Cursor to fully load

### Step 3: Open Developer Tools (Optional but Helpful)

1. In Cursor: **Help > Toggle Developer Tools**
2. Click **Console** tab
3. Look for MCP-related logs when you use chat

### Step 4: Open a NEW Cursor Chat

1. Click "New Chat" button (or press `⌘ + L`)
2. **Important:** This must be a fresh chat, not this conversation

### Step 5: Test with These Queries

Try each of these and watch for tool usage:

```
1. "List all repositories indexed by LocalAST"
   Expected tool: list_repositories
   
2. "Find the parse_file function"
   Expected tool: search_code
   
3. "Show me statistics for the localast repository"
   Expected tool: get_repo_stats
   
4. "Find code related to semantic search"
   Expected tool: search_semantic
   
5. "What methods are in the LocalASTServer class?"
   Expected tool: get_symbol_tree or list_symbols_in_file
```

---

## 🔍 How to Tell if MCP is Working

### ✅ Good Signs:
- Tool badge/indicator appears in chat (e.g., "Using tool: search_code")
- Response comes back in < 2 seconds
- Specific file paths with exact line numbers (e.g., `parser.py:363`)
- Structured data (tables, code blocks)
- Mentions "LocalAST" or tool names in response

### ❌ Bad Signs:
- No tool indicator
- Generic/vague responses
- "I don't have access to..." messages
- Takes > 5 seconds to respond
- No specific line numbers or file paths

---

## 🐛 Troubleshooting

### Problem: Cursor doesn't seem to use MCP tools

**Solution 1:** Check Developer Console
1. Help > Toggle Developer Tools > Console
2. Type `mcp` in the filter
3. Look for connection errors or tool invocation logs

**Solution 2:** Restart Cursor Properly
- Must use ⌘ + Q (full quit), not just close window
- Wait 5+ seconds before reopening

**Solution 3:** Test MCP Server Directly
```bash
cd /Users/viswanathsekar/localast
.venv/bin/python test_mcp_protocol.py
```
Should show "✅ MCP Server is properly configured and working!"

**Solution 4:** Check Cursor Logs
```bash
# macOS logs location:
tail -f ~/Library/Logs/Cursor/*.log | grep -i mcp
```

### Problem: "command not found: localast"

**Solution:** Check if localast is installed in venv:
```bash
ls -la /Users/viswanathsekar/localast/.venv/bin/localast
```

If missing:
```bash
cd /Users/viswanathsekar/localast
source .venv/bin/activate
pip install -e .
```

### Problem: "Connection refused" or "Server not responding"

**Solution:** Background server might be interfering:
```bash
# Kill any running instances
pkill -f "localast serve"

# Cursor will start it automatically when needed
```

---

## 📊 Validation Queries Reference

### Basic Search (Tests: FTS indexing)
```
- "Find all functions in localast"
- "Search for embedding in the code"
- "Where is the database connection defined?"
```

### Semantic Search (Tests: Vector embeddings)
```
- "Find code that handles vector similarity"
- "Show me error handling patterns"
- "Find authentication-related code"
```

### Statistics (Tests: Repository indexing)
```
- "How many files are indexed?"
- "Show me repository statistics"
- "List all indexed repositories"
```

### Hierarchical (Tests: Symbol trees)
```
- "What methods are in the EmbeddingEngine class?"
- "Show me the structure of the MCP server"
- "List symbols in cli.py"
```

### Dependencies (Tests: Call graphs)
```
- "What functions does parse_file call?"
- "Show me the call graph for index_code_paths"
- "What depends on the database module?"
```

### Git History (Tests: Version tracking)
```
- "What changed in the last 5 commits?"
- "Show me recent changes to parser.py"
- "When was the MCP server introduced?"
```

---

## 🎉 Success Indicators

When MCP is working, you'll see responses like:

```
Using tool: search_code

Found parse_file function:
- File: src/localast/ast/parser.py
- Lines: 363-396
- Type: function
- Description: Parse a single file and extract symbols...

[Code snippet shown with line numbers]
```

**That's it! Your MCP server is ready to use!** 🚀


