# Gamma MCP Server

Model Context Protocol server for [Gamma.app](https://gamma.app). Exposes tools to create presentations, documents, webpages, and social posts via Gamma's API. Works with any MCP-compatible AI assistant (Claude Code, Claude Desktop, OpenCode, GitHub Copilot CLI, Gemini CLI).

## Quick Start

```bash
npm install
npm run build
```

Set `GAMMA_API_KEY` environment variable to your Gamma API key (format: `sk-gamma-xxxxxxxx`), then configure your AI assistant to use the MCP server at `dist/index.js`.

## Project Structure

```
src/
├── index.ts          # Bootstrap: MCP server + stdio transport + tool registration
├── constants.ts      # API base URL, timeouts, limits, error messages
├── types.ts          # TypeScript interfaces for API requests/responses
├── schemas/index.ts  # Zod validation schemas for all tool inputs
├── services/
│   ├── gamma-client.ts  # HTTP client for Gamma API (axios)
│   └── formatters.ts    # Output formatters (markdown / json)
└── tools/
    ├── generate.ts  # gamma_generate, gamma_get_status, gamma_from_template
    ├── list.ts      # gamma_list_themes, gamma_list_folders
    ├── share.ts     # gamma_share_email
    └── index.ts     # Re-exports tool registration functions
```

## Available Tools

| Tool | Description |
|------|-------------|
| `gamma_generate` | Create presentations, documents, webpages, social posts |
| `gamma_get_status` | Poll generation progress (with optional auto-poll) |
| `gamma_from_template` | Remix existing Gamma templates with variables |
| `gamma_list_themes` | Browse available visual themes |
| `gamma_list_folders` | List your Gamma folders |
| `gamma_share_email` | Share content via email |
| `gamma_health` | Liveness probe — verify API key and server reachability |
| `gamma_archive` | Archive a Gamma from the workspace |

## Architecture Notes

- `GammaClient` (gamma-client.ts) is the single API client — all tool implementations call through it
- `createGammaClient()` (gamma-client.ts line 248) is the factory — validates key presence and format, throws with helpful message if misconfigured
- Polling is handled inside `GammaClient.waitForCompletion()` — tools just set `waitForCompletion: true` to activate
- Error handling is centralized in `GammaClient.handleError()` — status codes mapped to user-safe messages (no raw API data leaked)
- Output formatting is stateless — `formatGenerationOutput`, `formatThemesOutput`, `formatFoldersOutput`, `formatShareOutput` in formatters.ts
- All Zod schemas use `.strict()` to reject unknown fields

## Adding New Tools

1. Add method to `GammaClient` in `services/gamma-client.ts`
2. Create tool in `tools/*.ts` using `server.registerTool()`
3. Register in `src/tools/index.ts` export
4. Register in `src/index.ts` via the appropriate `register*()` call
5. Add Zod schema in `schemas/index.ts`
6. Add formatter in `services/formatters.ts` if needed

## Testing

Run `npm test` — uses Node.js built-in test runner (`node --test`). Test files live in `src/__tests__/`.