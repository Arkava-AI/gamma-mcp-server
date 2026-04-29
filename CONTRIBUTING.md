# Contributing to Gamma MCP Server

Thank you for contributing. Here's how to get your changes merged in.

## Development Setup

```bash
git clone https://github.com/Arkava-AI/gamma-mcp-server
cd gamma-mcp-server
npm install
```

## Commands

| Command | Purpose |
|---|---|
| `npm run dev` | Run in watch mode with auto-reload |
| `npm run build` | Compile TypeScript to `dist/` |
| `npm run lint` | Run ESLint |
| `npm run format` | Format code with Prettier |
| `npm run typecheck` | Type check without emitting |
| `npm test` | Run tests |
| `npm run coverage` | Run tests with coverage report |
| `npm run inspect` | Open MCP Inspector |

## Code Style

- ESLint + Prettier enforce style — run both before committing
- `npm run lint:fix` applies auto-fixes
- `npm run format` formats all source files

## Adding New Tools

1. Add method to `GammaClient` in `src/services/gamma-client.ts`
2. Create tool in `src/tools/<name>.ts` using `server.registerTool()`
3. Register in `src/tools/index.ts` export
4. Register in `src/index.ts` via the appropriate `register*()` call
5. Add Zod schema in `src/schemas/index.ts`
6. Add formatter in `src/services/formatters.ts` if needed

## Tool Annotations

Always set MCP tool annotations:

```typescript
annotations: {
  readOnlyHint: true,        // Does not modify server state
  destructiveHint: false,    // Destructive to server state
  idempotentHint: true,      // Safe to retry
  openWorldHint: false,      // No external network calls beyond Gamma API
},
```

## Tests

Add tests for all new schemas in `src/__tests__/schemas.test.ts`. Run tests with `npm test`.

## Commit Messages

Prefix commits with type:

- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation only
- `refactor:` code restructure with no behaviour change
- `test:` adding or updating tests
- `chore:` maintenance, deps, CI config

## Pull Request Process

1. Fork the repo and create a feature branch
2. Make your changes + add tests
3. Ensure all checks pass (`npm run build && npm run lint && npm run typecheck && npm test`)
4. Open a PR with a clear description

## Security

Do not commit API keys, credentials, or tokens. The Gamma API key is never logged or echoed back to clients.
