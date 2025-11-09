#!/usr/bin/env python3
"""Test MCP server using the actual MCP protocol library."""

import asyncio
import sys
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

async def test_server():
    """Test the MCP server."""
    from localast.config import LocalConfig
    from localast.mcp.server import create_server
    
    print("=" * 80)
    print("LocalAST MCP Server Protocol Test")
    print("=" * 80)
    print()
    
    # Create server
    print("1. Creating server...")
    config = LocalConfig()
    server = create_server(config)
    print(f"   ✅ Server created")
    print(f"   Database: {config.resolved_database_path()}")
    print()
    
    # Check tools registered
    print("2. Checking registered tools...")
    print(f"   Registered tools: {len(server.tools)}")
    print(f"   Tool metadata: {len(server.tool_metadata)}")
    print()
    
    if server.tools:
        print("3. Available tools:")
        for i, (name, (desc, schema)) in enumerate(server.tool_metadata.items(), 1):
            if i <= 10:  # Show first 10
                print(f"   {i:2d}. {name}")
                print(f"       {desc[:70]}")
            elif i == 11:
                print(f"   ... and {len(server.tool_metadata) - 10} more")
                break
        print()
    else:
        print("   ❌ No tools registered!")
        return False
    
    # Test a tool directly
    print("4. Testing search_code tool directly...")
    if "search_code" in server.tools:
        try:
            connection = server._get_connection()
            handler = server.tools["search_code"]
            result = handler(connection, {"query": "parse_file", "kind": "function"})
            print(f"   ✅ Tool executed successfully")
            print(f"   Result preview: {str(result)[:200]}...")
            print()
            return True
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    else:
        print("   ❌ search_code tool not found")
        return False

async def main():
    try:
        success = await test_server()
        
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        
        if success:
            print("✅ MCP Server is properly configured and working!")
            print()
            print("To use with Cursor:")
            print("1. Make sure you have this in ~/.cursor/mcp.json:")
            print("   {")
            print('     "mcpServers": {')
            print('       "localast": {')
            print(f'         "command": "{sys.executable.replace("/python3", "/localast")}",')
            print('         "args": ["serve"]')
            print('       }')
            print('     }')
            print("   }")
            print()
            print("2. Completely restart Cursor (⌘ + Q, then reopen)")
            print()
            print("3. Open a NEW Cursor Chat and ask:")
            print('   "Find the parse_file function in localast"')
            print()
            print("4. Look for tool usage indicators in the response")
            return 0
        else:
            print("❌ MCP Server has configuration issues")
            return 1
            
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))


