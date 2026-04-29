import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { GammaClient } from "../services/gamma-client.js";
import { HealthInputSchema, HealthInput } from "../schemas/index.js";

export function registerHealthTools(
  server: McpServer,
  client: GammaClient
): void {
  server.registerTool(
    "gamma_health",
    {
      title: "Health Check",
      description: `Check if the Gamma MCP server and API are reachable and working.

Use this to verify your configuration is correct before running other tools. Returns whether the API key is valid, the API is reachable, and the account status.

Useful for:
- Confirming the server is running after startup
- Troubleshooting connection issues
- Verifying your GAMMA_API_KEY is valid`,
      inputSchema: HealthInputSchema,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async (_params: HealthInput) => {
      const result = await client.healthCheck();
      const text = result.healthy
        ? `# ✅ Server Healthy\n\n${result.message}`
        : `# ❌ Server Unhealthy\n\n${result.message}`;

      return {
        content: [{ type: "text" as const, text }],
      };
    }
  );
}