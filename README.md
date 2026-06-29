# Armoriq

AI Agent Security Platform with MCP Support.

## Quick Start

```bash
pnpm install
docker-compose up
```

Or for development:

```bash
# Terminal 1 - Agent
cd apps/agent && uv run python -m src.main

# Terminal 2 - Dashboard
cd apps/web && pnpm dev
```

## Environment Variables

Create `.env` in `apps/agent/`:
```
GEMINI_API_KEY=your_key_here
DATABASE_URL=sqlite:///./armoriq.db
```
