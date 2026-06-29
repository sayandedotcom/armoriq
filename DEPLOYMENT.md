# Deployment Instructions for Armoriq

## Service Split

| Component | Deployment | Reason |
|-----------|------------|--------|
| `apps/web` (Next.js) | **Vercel** | Native Next.js support, edge deployment |
| `apps/agent` (FastAPI) | **Railway/Render/Fly** | Long-lived WS + stdio subprocess |
| `apps/mcp-bank` | **Co-located with agent** | Spawned as subprocess by agent |

## Vercel (Dashboard)

```bash
cd apps/web
vercel deploy
```

Environment variables:
- `NEXT_PUBLIC_WS_URL` = `ws://your-railway-app.railway.app/ws`

## Railway (Agent + MCP Bank)

1. Create new Railway project
2. Connect GitHub repo
3. Set root to `apps/agent`
4. Add start command: `uv run fastapi run src/main.py --port 8000`

Environment variables:
- `GEMINI_API_KEY`
- `TAVILY_API_KEY`
- `DATABASE_URL` = `sqlite:///./armoriq.db`

## MCP Server (mcp-bank)

Started automatically by the agent as a subprocess via stdio transport. No separate deployment needed.

## Verification

After deployment:
1. Dashboard loads at Vercel URL
2. Agent WebSocket connects to Railway URL
3. Tools discovered from mcp-bank + Tavily
4. Policy engine evaluates tool calls
5. Dashboard reflects real-time changes
