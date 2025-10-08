import os, json, asyncio
from mcp.server.fastmcp import FastMCP
from tavily import TavilyClient
from dotenv import load_dotenv
load_dotenv()

mcp= FastMCP("tavily_search")
tavily_client = TavilyClient(api_key=os.getenv('TAVILY_API_KEY'))

@mcp.tool()
def websearch_tool(query: str) -> str:
    """MCP server based Websearch tool"""
    try:
        results = tavily_client.search(query=query,max_results=3,search_depth = "basic")
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error: {str(e)}"

async def main():
    """Main function to run the mcp server!!"""
    await mcp.run_stdio_async()

if __name__ == "__main__":
    asyncio.run(main())