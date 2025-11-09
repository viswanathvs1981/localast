#!/usr/bin/env python3
"""Test MCP server directly to verify it responds to requests."""

import json
import subprocess
import sys

def send_mcp_request(request):
    """Send a JSON-RPC request to the MCP server."""
    # Start the MCP server
    proc = subprocess.Popen(
        ["/Users/viswanathsekar/localast/.venv/bin/localast", "serve"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    try:
        # Send request
        request_str = json.dumps(request) + "\n"
        proc.stdin.write(request_str)
        proc.stdin.flush()
        
        # Read response (read multiple lines until we get a valid JSON)
        response_lines = []
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            response_lines.append(line)
            try:
                response = json.loads(line)
                return response
            except json.JSONDecodeError:
                continue
        
        # If we didn't get a response, check stderr
        stderr = proc.stderr.read()
        return {"error": f"No valid response. Lines: {response_lines}, Stderr: {stderr}"}
    
    finally:
        proc.terminate()
        proc.wait(timeout=2)

def test_list_tools():
    """Test if server can list available tools."""
    print("=" * 80)
    print("TEST 1: List Available Tools")
    print("=" * 80)
    
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list"
    }
    
    response = send_mcp_request(request)
    print("Response:")
    print(json.dumps(response, indent=2))
    
    if "result" in response and "tools" in response["result"]:
        tools = response["result"]["tools"]
        print(f"\n✅ Found {len(tools)} tools:")
        for tool in tools[:5]:  # Show first 5
            print(f"  - {tool['name']}: {tool.get('description', 'N/A')[:60]}")
        if len(tools) > 5:
            print(f"  ... and {len(tools) - 5} more")
        return True
    else:
        print("❌ Failed to list tools")
        return False

def test_search_tool():
    """Test if server can execute a search tool."""
    print("\n" + "=" * 80)
    print("TEST 2: Execute search_code Tool")
    print("=" * 80)
    
    request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "search_code",
            "arguments": {
                "query": "parse_file",
                "kind": "function"
            }
        }
    }
    
    response = send_mcp_request(request)
    print("Response:")
    print(json.dumps(response, indent=2))
    
    if "result" in response:
        print("\n✅ Tool executed successfully")
        return True
    else:
        print("❌ Tool execution failed")
        return False

def main():
    print("LocalAST MCP Server Direct Test")
    print("=" * 80)
    print()
    
    # Test 1: Can server list tools?
    test1_passed = test_list_tools()
    
    # Test 2: Can server execute a tool?
    test2_passed = test_search_tool()
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"List Tools:     {'✅ PASS' if test1_passed else '❌ FAIL'}")
    print(f"Execute Tool:   {'✅ PASS' if test2_passed else '❌ FAIL'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 MCP Server is working correctly!")
        print("\nIf Cursor still doesn't use it, try:")
        print("1. Completely quit Cursor (⌘ + Q)")
        print("2. Reopen Cursor")
        print("3. Open Developer Tools (Help > Toggle Developer Tools)")
        print("4. Look for MCP-related logs in Console")
    else:
        print("\n⚠️  MCP Server has issues - check the errors above")
    
    return 0 if (test1_passed and test2_passed) else 1

if __name__ == "__main__":
    sys.exit(main())


