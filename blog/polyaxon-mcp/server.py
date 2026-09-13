"""Local stdio server using the official MCP Python SDK v2 API."""

from mcp.server import MCPServer

from adapter import Adapter, SubmitRequest

mcp = MCPServer("Polyaxon evaluation adapter")
adapter = Adapter()


@mcp.tool()
def submit_evaluation(request: SubmitRequest) -> dict:
    """Submit one approved evaluation; reuse a request key only for identical work."""
    return adapter.submit(request.model_dump())


@mcp.tool()
def evaluation_status(request_id: str) -> dict:
    """Inspect an evaluation owned by this operator-assigned identity."""
    return adapter.inspect(request_id)


if __name__ == "__main__":
    mcp.run(transport="stdio")
