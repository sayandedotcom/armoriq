# ArmorIQ

AI Agent Security Platform with MCP (Model Context Protocol) Support. ArmorIQ provides a policy layer that sits between an LLM and its tools, deciding what is and isn't allowed.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      ArmorIQ Platform                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────────┐    ┌──────────────┐  │
│  │    Web      │◄──►│     Agent       │◄──►│   MCP Bank   │  │
│  │  Dashboard  │    │   (FastAPI)     │    │  (MCP Server)│  │
│  │  (Next.js)  │    │                 │    │              │  │
│  │   :3000     │    │    :8000        │    │   stdio      │  │
│  └─────────────┘    └─────────────────┘    └──────────────┘  │
│         ▲                   ▲                                │
│         │                   │                                │
│         └───────── WebSocket ────────────────┘               │
│                    (Real-time updates)                        │
└─────────────────────────────────────────────────────────────┘
```

## Features

- **Policy Engine**: Create guardrail rules (block tools, require approval, input validation, token budgets)
- **Real-time Enforcement**: Rules take effect immediately via WebSocket
- **MCP Integration**: Connect to MCP servers with live tool discovery
- **Approval Workflow**: Human-in-the-loop for sensitive operations
- **Activity Logging**: Full audit trail of agent decisions

## Prerequisites

- Node.js >= 18
- pnpm >= 9
- Python >= 3.11
- Gemini API key (or another LLM provider)

## Quick Start

### 1. Install Dependencies

```bash
pnpm install
```

### 2. Configure Environment

Create `.env` in `apps/agent/`:

```env
GEMINI_API_KEY=your_gemini_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here  # optional
DATABASE_URL=sqlite:///./armoriq.db
```

### 3. Start Development Servers

```bash
pnpm dev
```

This starts all services:
- **Web Dashboard**: http://localhost:3000
- **Agent API**: http://localhost:8000
- **MCP Bank**: stdio connection

## Docker Deployment

```bash
# Set environment variables
export GEMINI_API_KEY=your_key_here
export TAVILY_API_KEY=your_key_here

# Start all services
docker-compose up
```

## Development

### Running Services Individually

```bash
# Terminal 1 - Agent backend
cd apps/agent && PYTHONPATH=./src uv run uvicorn src.main:app --port 8000 --reload

# Terminal 2 - MCP Bank (custom MCP server)
cd apps/mcp-bank && uv run python -m mcp_bank

# Terminal 3 - Web dashboard
cd apps/web && pnpm dev
```

### Running Tests

```bash
# Agent tests
cd apps/agent && uv run pytest
```

## Project Structure

```
armoriq/
├── apps/
│   ├── agent/           # FastAPI agent backend
│   │   ├── src/
│   │   │   ├── agent/   # LLM and tool execution
│   │   │   ├── policy/  # Policy engine
│   │   │   └── transport/ # MCP transport manager
│   │   └── servers.json # MCP server configuration
│   ├── mcp-bank/        # Custom MCP server
│   │   └── mcp_bank/   # MCP tools implementation
│   └── web/             # Next.js dashboard
│       ├── app/         # App router pages
│       └── src/         # React components
└── packages/
    └── shared-types/    # Shared TypeScript types
```

## MCP Servers

### Custom MCP Bank

The custom MCP server exposes tools for:
- CRUD operations on a mini database
- File management operations

### Remote MCP Servers

Configure additional MCP servers in `apps/agent/servers.json`:

```json
{
  "name": "context7",
  "transport": "sse",
  "url": "https://api.context7.io/mcp"
}
```

## Policy Rule Types

| Type | Description |
|------|-------------|
| `block_tool` | Permanently block a tool |
| `require_approval` | Block until human approves |
| `input_validation` | Validate tool arguments |
| `token_budget` | Limit token usage |
| `prompt_injection_guard` | Detect prompt injection |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/rules` | List all rules |
| POST | `/rules` | Create rule |
| PUT | `/rules/{id}` | Update rule |
| DELETE | `/rules/{id}` | Delete rule |
| GET | `/approvals` | List pending approvals |
| POST | `/approvals` | Approve/reject |
| GET | `/logs` | Activity logs |
| POST | `/chat` | Send message to agent |
| WS | `/ws` | WebSocket for real-time updates |

## Tech Stack

- **Agent**: FastAPI, Python, Google Gemini
- **Dashboard**: Next.js 14, TypeScript, Tailwind CSS, Radix UI
- **Database**: SQLite (file-based, no setup required)
- **Protocol**: Model Context Protocol (MCP)
