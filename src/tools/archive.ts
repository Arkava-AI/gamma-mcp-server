import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { GammaClient } from "../services/gamma-client.js";
import { ArchiveInputSchema, ArchiveInput } from "../schemas/index.js";

export function registerArchiveTools(
  server: McpServer,
  client: GammaClient
): void {
  server.registerTool(
    "gamma_archive",
    {
      title: "Archive Gamma",
      description: `Archive a Gamma (presentation, document, webpage, or social post) from your workspace.

Archived content is removed from your active workspace but retained for recovery. Use this to declutter your Gamma dashboard.`,
      inputSchema: ArchiveInputSchema,
      annotations: {
        readOnlyHint: false,
        destructiveHint: true,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
async (_params: ArchiveInput) => {
      const { gammaId } = _params;
      const result = await client.archive(gammaId);
      return {
        content: [
          {
            type: "text" as const,
            text: result.archived
              ? `# ✅ Archived\n\nGamma \`${gammaId}\` has been archived.`
              : `# ⚠️ Not Archived\n\nGamma \`${gammaId}\` could not be archived.`,
          },
        ],
      };
    }
  );
}