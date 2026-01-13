#!/usr/bin/env node
/**
 * Gamma MCP Server
 *
 * A Model Context Protocol server for Gamma.app API integration.
 * Enables Claude Desktop to create presentations, documents, webpages,
 * and social posts using Gamma's AI-powered content generation.
 *
 * @author Amer Altaf <amer@arkava.ai>
 * @license MIT
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createGammaClient } from "./services/gamma-client.js";
import {
  registerGenerationTools,
  registerListTools,
  registerShareTools,
} from "./tools/index.js";

/**
 * Server metadata
 */
const SERVER_NAME = "gamma-mcp-server";
const SERVER_VERSION = "1.0.0";

/**
 * Initialize and start the MCP server
 */
async function main(): Promise<void> {
  // Validate API key is present
  let client;
  try {
    client = createGammaClient();
  } catch (error) {
    console.error(
      `ERROR: ${error instanceof Error ? error.message : String(error)}`
    );
    console.error("");
    console.error("To configure your Gamma API key:");
    console.error("1. Get your API key from https://gamma.app/settings (API tab)");
    console.error("2. Set the GAMMA_API_KEY environment variable");
    console.error("");
    console.error("Example Claude Desktop config (claude_desktop_config.json):");
    console.error(
      JSON.stringify(
        {
          mcpServers: {
            gamma: {
              command: "node",
              args: ["/path/to/gamma-mcp-server/dist/index.js"],
              env: {
                GAMMA_API_KEY: "sk-gamma-your-api-key-here",
              },
            },
          },
        },
        null,
        2
      )
    );
    process.exit(1);
  }

  // Create MCP server instance
  const server = new McpServer({
    name: SERVER_NAME,
    version: SERVER_VERSION,
  });

  // Register all tools
  registerGenerationTools(server, client);
  registerListTools(server, client);
  registerShareTools(server, client);

  // Connect to stdio transport for Claude Desktop
  const transport = new StdioServerTransport();
  await server.connect(transport);

  // Log startup (to stderr to not interfere with MCP protocol on stdout)
  console.error(`${SERVER_NAME} v${SERVER_VERSION} started`);
  console.error("Available tools:");
  console.error("  - gamma_generate: Create presentations, documents, webpages, social posts");
  console.error("  - gamma_get_status: Check generation progress");
  console.error("  - gamma_from_template: Remix existing templates");
  console.error("  - gamma_list_themes: Browse available themes");
  console.error("  - gamma_list_folders: List your folders");
  console.error("  - gamma_share_email: Share content via email");
}

// Run the server
main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
