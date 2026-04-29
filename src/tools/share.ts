/**
 * Share Tools
 *
 * Tools for sharing Gamma content.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { GammaClient } from "../services/gamma-client.js";
import { ShareEmailInputSchema, ShareEmailInput } from "../schemas/index.js";
import { formatShareOutput } from "../services/formatters.js";

/**
 * Register share tools on the MCP server
 */
export function registerShareTools(
  server: McpServer,
  client: GammaClient
): void {
  // ============================================================================
  // gamma_share_email - Share content via email
  // ============================================================================
  server.registerTool(
    "gamma_share_email",
    {
      title: "Share Gamma via Email",
      description: `Share a generated Gamma with recipients via email.

Send an email invitation to view your Gamma content. Recipients will receive a link to access the content.

PARAMETERS:
- generationId (required): The ID of the Gamma to share
- emails (required): Array of email addresses (max 10)
- message: Optional personal message to include

RETURNS:
- success: Whether the share was successful
- emails: List of recipients

EXAMPLE:
{
  generationId: "gen_abc123",
  emails: ["colleague@company.com", "client@example.com"],
  message: "Here's the presentation we discussed"
}

NOTE: Ensure the generation is complete before sharing. Use waitForCompletion: true to automatically wait up to 5 minutes.`,
      inputSchema: ShareEmailInputSchema,
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: true,
      },
    },
    async (params: ShareEmailInput) => {
      try {
        if (params.waitForCompletion) {
          await client.waitForCompletion(params.generationId);
        }

        const response = await client.shareEmail(
          params.generationId,
          params.emails,
          params.message
        );

        const formatted = formatShareOutput(
          response.success,
          params.emails,
          params.response_format
        );

        return {
          content: [{ type: "text" as const, text: formatted.text }],
        };
      } catch (error) {
        return {
          content: [
            {
              type: "text" as const,
              text: `Error sharing content: ${error instanceof Error ? error.message : String(error)}`,
            },
          ],
        };
      }
    }
  );
}
