/**
 * List Tools
 *
 * Tools for browsing themes and folders.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { GammaClient } from "../services/gamma-client.js";
import {
  ListThemesInputSchema,
  ListFoldersInputSchema,
  ListThemesInput,
  ListFoldersInput,
} from "../schemas/index.js";
import {
  formatThemesOutput,
  formatFoldersOutput,
} from "../services/formatters.js";

/**
 * Register list tools on the MCP server
 */
export function registerListTools(
  server: McpServer,
  client: GammaClient
): void {
  // ============================================================================
  // gamma_list_themes - List available visual themes
  // ============================================================================
  server.registerTool(
    "gamma_list_themes",
    {
      title: "List Gamma Themes",
      description: `List available visual themes for Gamma content.

Themes control the visual styling of generated content including colors, fonts, and layouts. Use the returned theme IDs with gamma_generate's themeId parameter.

PARAMETERS:
- limit: Max themes to return (1-100, default 20)
- offset: Skip this many themes for pagination

RETURNS:
- items: Array of themes with id, name, description
- total: Total number of themes available
- hasMore: Whether more themes are available
- nextOffset: Offset for next page

EXAMPLE:
{ limit: 10, response_format: "markdown" }`,
      inputSchema: ListThemesInputSchema,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: true,
      },
    },
    async (params: ListThemesInput) => {
      try {
        const response = await client.listThemes({
          limit: params.limit,
          offset: params.offset,
        });

        const formatted = formatThemesOutput(
          response.themes,
          response.total,
          params.offset,
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
              text: `Error listing themes: ${error instanceof Error ? error.message : String(error)}`,
            },
          ],
        };
      }
    }
  );

  // ============================================================================
  // gamma_list_folders - List user folders
  // ============================================================================
  server.registerTool(
    "gamma_list_folders",
    {
      title: "List Gamma Folders",
      description: `List your Gamma folders for organizing content.

Folders help organize generated content. Use the returned folder IDs with gamma_generate's folderId parameter to save content to specific folders.

PARAMETERS:
- limit: Max folders to return (1-100, default 20)
- offset: Skip this many folders for pagination

RETURNS:
- items: Array of folders with id, name, itemCount
- total: Total number of folders
- hasMore: Whether more folders are available
- nextOffset: Offset for next page

EXAMPLE:
{ limit: 20, response_format: "json" }`,
      inputSchema: ListFoldersInputSchema,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: true,
      },
    },
    async (params: ListFoldersInput) => {
      try {
        const response = await client.listFolders({
          limit: params.limit,
          offset: params.offset,
        });

        const formatted = formatFoldersOutput(
          response.folders,
          response.total,
          params.offset,
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
              text: `Error listing folders: ${error instanceof Error ? error.message : String(error)}`,
            },
          ],
        };
      }
    }
  );
}
