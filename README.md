# Gamma MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node.js Version](https://img.shields.io/badge/node-%3E%3D18-brightgreen)](https://nodejs.org)
[![MCP SDK](https://img.shields.io/badge/MCP%20SDK-1.6.1-blue)](https://modelcontextprotocol.io)

A Model Context Protocol (MCP) server that integrates [Gamma.app](https://gamma.app) with AI assistants. Create presentations, documents, webpages, and social posts directly from your AI conversations.

Works with: **Claude Code**, **Claude Desktop**, **OpenCode**, **GitHub Copilot CLI**, **Google Gemini CLI**, and any other MCP-compatible AI assistant.

## Features

- **Generate Content**: Create professional presentations, documents, webpages, and social posts from text prompts
- **Theme Support**: Browse and apply visual themes to your content
- **Folder Organization**: Save generated content to specific folders
- **Template Remix**: Create variations of existing Gamma templates
- **Email Sharing**: Share generated content directly via email

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/Arkava-AI/gamma-mcp-server.git
cd gamma-mcp-server
npm install
npm run build
```

### 2. Get Your Gamma API Key

1. Log in to [gamma.app](https://gamma.app)
2. Go to **Settings > API** (or Settings > Members > API tab)
3. Click **Create API key**
4. Copy the key (format: `sk-gamma-xxxxxxxx`)

> **Note**: Requires Gamma Pro, Ultra, Team, or Business account.

### 3. Configure Your AI Assistant

Choose your AI assistant below for setup instructions.

---

## Claude Desktop (macOS / Windows / Linux)

### Config File

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

Add to the `mcpServers` object:

```json
{
  "mcpServers": {
    "gamma": {
      "command": "node",
      "args": ["/absolute/path/to/gamma-mcp-server/dist/index.js"],
      "env": {
        "GAMMA_API_KEY": "sk-gamma-your-api-key-here"
      }
    }
  }
}
```

### Restart Claude Desktop

Restart Claude Desktop to load the new MCP server. You should see "gamma" in your MCP servers list.

---

## Claude Code

Claude Code uses the same MCP configuration as Claude Desktop. If you've already configured Claude Desktop, you're all set.

For **project-level configuration**, create a `.claude/settings.json` file in your project directory with the same `mcpServers` structure shown above. This allows different projects to use different MCP server configurations.

---

## OpenCode

### Config File

| Scope | Path |
|---|---|
| Global (user) | `~/.config/opencode/opencode.json` |
| Project | `./opencode.json` (in your project root) |

### JSON Structure

```json
{
  "mcp": {
    "gamma": {
      "type": "local",
      "command": ["node", "/absolute/path/to/gamma-mcp-server/dist/index.js"],
      "enabled": true,
      "environment": {
        "GAMMA_API_KEY": "sk-gamma-your-api-key-here"
      }
    }
  }
}
```

> **Note**: OpenCode uses a different config format from Claude Desktop — `mcp` (not `mcpServers`), `type` field required (`"local"` or `"remote"`), `command` is an array, and env vars go under `environment`.

Restart OpenCode after editing the config to load the server.

---

## GitHub Copilot CLI

### Config File

- `~/.copilot/mcp-config.json`

### JSON Structure

```json
{
  "mcpServers": {
    "gamma": {
      "type": "local",
      "command": "node",
      "args": ["/absolute/path/to/gamma-mcp-server/dist/index.js"],
      "env": {
        "GAMMA_API_KEY": "sk-gamma-your-api-key-here"
      },
      "tools": ["*"]
    }
  }
}
```

> **Note**: Requires the GitHub Copilot CLI (`gh copilot`) — not the same as OpenAI Codex.

---

## OpenAI Codex

### Config File

- `~/.codex/config.toml` (TOML format, not JSON)

### TOML Structure

```toml
[mcp_servers.gamma]
command = "node"
args = ["/absolute/path/to/gamma-mcp-server/dist/index.js"]
enabled = true

[mcp_servers.gamma.env]
GAMMA_API_KEY = "sk-gamma-your-api-key-here"
```

> **Note**: Codex uses TOML format, not JSON. The `env` section is a separate table under `[mcp_servers.gamma.env]`.

---

## Google Gemini CLI

### Config File

| Scope | Path |
|---|---|
| User | `~/.gemini/settings.json` |
| Project | `.gemini/settings.json` (in your project root) |

### JSON Structure

```json
{
  "mcpServers": {
    "gamma": {
      "command": "node",
      "args": ["/absolute/path/to/gamma-mcp-server/dist/index.js"],
      "cwd": "/absolute/path/to/gamma-mcp-server",
      "env": {
        "GAMMA_API_KEY": "sk-gamma-your-api-key-here"
      },
      "timeout": 30000
    }
  }
}
```

Restart Gemini CLI after editing the config to load the server.

---

## Available Tools

| Tool | Description |
|------|-------------|
| `gamma_generate` | Create presentations, documents, webpages, or social posts |
| `gamma_get_status` | Check generation progress (with optional polling) |
| `gamma_from_template` | Remix existing Gamma templates |
| `gamma_list_themes` | Browse available visual themes |
| `gamma_list_folders` | List your Gamma folders |
| `gamma_share_email` | Share content via email |
| `gamma_health` | Verify server and API are reachable |
| `gamma_archive` | Archive a Gamma from your workspace |

### gamma_generate

Create new content using Gamma's AI.

**Formats & Sizes:**
- `presentation`: fluid, 16x9, 4x3
- `document`: fluid, pageless, letter, a4
- `social`: 1x1, 4x5, 9x16
- `webpage`: fluid

**Example prompts in your AI assistant:**
- "Create a 5-slide presentation about sustainable energy"
- "Generate a document explaining our Q1 results"
- "Make a social media post announcing our new product"

### gamma_get_status

Check if a generation has completed. Set `waitForCompletion: true` to automatically poll until done.

### gamma_from_template

Remix an existing Gamma with new content or variable substitutions.

```json
{
  "templateId": "gamma_xyz789",
  "prompt": "Update for Q1 2025",
  "variables": { "company_name": "Acme Corp" }
}
```

---

## Multi-Machine Setup

This repository is designed for easy deployment across multiple machines:

```bash
# On each machine:
git clone https://github.com/Arkava-AI/gamma-mcp-server.git
cd gamma-mcp-server
npm install && npm run build

# Then configure your AI assistant with the local path
```

To update on any machine:
```bash
git pull
npm install
npm run build
# Restart your AI assistant
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GAMMA_API_KEY` | (required) | Your Gamma API key (`sk-gamma-...`) |
| `GAMMA_API_BASE_URL` | `https://public-api.gamma.app/v1.0` | Override for self-hosted Gamma instances |
| `GAMMA_POLL_INTERVAL_MS` | `2000` | Milliseconds between status polls (default 2s) |
| `GAMMA_MAX_POLL_ATTEMPTS` | `150` | Max polling attempts before timeout (default 150 × 2s = 5 min) |

---

## Development

```bash
# Run in development mode with auto-reload
npm run dev

# Build for production
npm run build

# Run linting
npm run lint

# Format code
npm run format

# Type check
npm run typecheck

# Test with MCP Inspector
npm run inspect
```

---

## Project Structure

```
gamma-mcp-server/
├── src/
│   ├── index.ts          # Main entry point
│   ├── constants.ts      # Configuration constants
│   ├── types.ts          # TypeScript interfaces
│   ├── schemas/          # Zod validation schemas
│   ├── services/         # API client and formatters
│   └── tools/            # MCP tool implementations
├── dist/                 # Compiled JavaScript (generated)
├── package.json
├── tsconfig.json
└── eslint.config.js
```

---

## API Credits

Gamma uses a credit-based system for API usage. Credits are consumed per generation. Monitor your usage in the [Gamma dashboard](https://gamma.app/settings) and enable auto-recharge if needed.

---

## Troubleshooting

| Error | Solution |
|-------|----------|
| "GAMMA_API_KEY environment variable is required" | Ensure `env.GAMMA_API_KEY` is set in your AI assistant's MCP config |
| "Invalid API key" | Keys should start with `sk-gamma-`. Verify the complete key. |
| "Rate limit exceeded" | Wait a few minutes. Contact Gamma support for higher limits. |
| "Insufficient credits" | Top up credits or enable auto-recharge in Gamma settings. |

---

## Requirements

- **Node.js 18+**
- **Gamma Pro/Ultra/Team/Business account** (for API access)
- **MCP-compatible AI assistant** (Claude Code, Claude Desktop, OpenCode, GitHub Copilot CLI, Gemini CLI, etc.)

---

## Maintainer

**Arkava Ltd** — [engage@arkava.ai](mailto:engage@arkava.ai)

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Links

- [Gamma Developer Docs](https://developers.gamma.app)
- [MCP Specification](https://modelcontextprotocol.io)
- [Gamma.app](https://gamma.app)