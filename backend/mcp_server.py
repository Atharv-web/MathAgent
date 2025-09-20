import os, json, asyncio
from mcp.server.fastmcp import FastMCP
from tavily import TavilyClient

mcp= FastMCP("tavily_search")

@mcp.tool()
def websearch_tool(query: str) -> str:
    """MCP server based Websearch tool"""
    tavily_client = TavilyClient(api_key=os.getenv('TAVILY_API_KEY'))
    try:
        results = tavily_client.search(query=query,max_results=3,search_depth = "basic")
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    asyncio.run(mcp.run(transport="stdio"))