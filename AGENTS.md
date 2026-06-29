# Armoriq Agent Instructions

## Project Structure

This is a Turborepo monorepo with three apps:
- `apps/web` - Next.js dashboard
- `apps/agent` - FastAPI agent backend
- `apps/mcp-bank` - Custom MCP server

## Development

```bash
# Install dependencies
pnpm install

# Start all services
pnpm dev

# Run agent tests
cd apps/agent && uv run pytest

# Run dashboard
cd apps/web && pnpm dev
```

## Environment Variables

Create `.env` in `apps/agent/`:
```
GEMINI_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here
DATABASE_URL=sqlite:///./armoriq.db
```

## Architecture Notes

- Agent uses manual tool-use loop (not LangGraph)
- Policy engine reads rules fresh per call (no restart needed)
- WebSocket broadcasts rule changes to dashboard
- MCP tools discovered live (no hardcoded lists)

## Adding New MCP Servers

Add to `apps/agent/servers.json`:
```json
{
  "name": "my-server",
  "transport": "stdio",
  "command": "python",
  "args": ["./path/to/server"]
}
```

Agent will discover and integrate tools automatically.
