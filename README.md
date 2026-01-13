# Gamma MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node.js Version](https://img.shields.io/badge/node-%3E%3D18-brightgreen)](https://nodejs.org)
[![MCP SDK](https://img.shields.io/badge/MCP%20SDK-1.6.1-blue)](https://modelcontextprotocol.io)

A Model Context Protocol (MCP) server that integrates [Gamma.app](https://gamma.app) with Claude Desktop. Create presentations, documents, webpages, and social posts directly from your Claude conversations.

## Features

- **Generate Content**: Create professional presentations, documents, webpages, and social posts from text prompts
- **Theme Support**: Browse and apply visual themes to your content
- **Folder Organization**: Save generated content to specific folders
- **Template Remix**: Create variations of existing Gamma templates
- **Email Sharing**: Share generated content directly via email

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/ArkavaLtd/gamma-mcp-server.git
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

### 3. Configure Claude Desktop

Add to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

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

### 4. Restart Claude Desktop

Restart Claude Desktop to load the new MCP server. You should see "gamma" in your MCP servers list.

## Available Tools

| Tool | Description |
|------|-------------|
| `gamma_generate` | Create presentations, documents, webpages, or social posts |
| `gamma_get_status` | Check generation progress (with optional polling) |
| `gamma_from_template` | Remix existing Gamma templates |
| `gamma_list_themes` | Browse available visual themes |
| `gamma_list_folders` | List your Gamma folders |
| `gamma_share_email` | Share content via email |

### gamma_generate

Create new content using Gamma's AI.

**Formats & Sizes:**
- `presentation`: fluid, 16x9, 4x3
- `document`: fluid, pageless, letter, a4
- `social`: 1x1, 4x5, 9x16
- `webpage`: fluid

**Example prompts in Claude:**
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
  "variables": { "company_name": "Arkava Ltd" }
}
```

## Multi-Machine Setup

This repository is designed for easy deployment across multiple machines:

```bash
# On each machine:
git clone https://github.com/ArkavaLtd/gamma-mcp-server.git
cd gamma-mcp-server
npm install && npm run build

# Then configure Claude Desktop with the local path
```

To update on any machine:
```bash
git pull
npm install
npm run build
# Restart Claude Desktop
```

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

## API Credits

Gamma uses a credit-based system for API usage. Credits are consumed per generation. Monitor your usage in the [Gamma dashboard](https://gamma.app/settings) and enable auto-recharge if needed.

## Troubleshooting

| Error | Solution |
|-------|----------|
| "GAMMA_API_KEY environment variable is required" | Ensure `env.GAMMA_API_KEY` is set in Claude Desktop config |
| "Invalid API key" | Keys should start with `sk-gamma-`. Verify the complete key. |
| "Rate limit exceeded" | Wait a few minutes. Contact Gamma support for higher limits. |
| "Insufficient credits" | Top up credits or enable auto-recharge in Gamma settings. |

## Requirements

- **Node.js 18+**
- **Gamma Pro/Ultra/Team/Business account** (for API access)
- **Claude Desktop** (for MCP integration)

## Author

**Amer Altaf** - [Arkava Ltd](https://arkava.ai)

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- [Gamma Developer Docs](https://developers.gamma.app)
- [MCP Specification](https://modelcontextprotocol.io)
- [Claude Desktop](https://claude.ai/download)
- [Gamma.app](https://gamma.app)
