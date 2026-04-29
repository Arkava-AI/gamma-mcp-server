/**
 * Generation Tools
 *
 * Tools for creating Gamma content (presentations, documents, webpages, social posts).
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { GammaClient } from "../services/gamma-client.js";
import {
  GenerateInputSchema,
  GetStatusInputSchema,
  FromTemplateInputSchema,
  GenerateInput,
  GetStatusInput,
  FromTemplateInput,
} from "../schemas/index.js";
import { formatGenerationOutput } from "../services/formatters.js";
import {
  GAMMA_FORMATS,
  PRESENTATION_SIZES,
  DOCUMENT_SIZES,
  SOCIAL_SIZES,
  IMAGE_STYLES,
  CARD_DENSITY,
} from "../constants.js";
import { GammaSize } from "../types.js";

/**
 * Register generation tools on the MCP server
 */
export function registerGenerationTools(
  server: McpServer,
  client: GammaClient
): void {
  // ============================================================================
  // gamma_generate - Create new content
  // ============================================================================
  server.registerTool(
    "gamma_generate",
    {
      title: "Generate Gamma Content",
      description: `Create a new presentation, document, webpage, or social post using Gamma's AI.

This tool generates professional content from any text input - a one-line prompt, messy notes, or polished content. Gamma's AI will structure, design, and style your content automatically.

SUPPORTED FORMATS:
- presentation: Slide decks (sizes: ${PRESENTATION_SIZES.join(", ")})
- document: Reports, articles, essays (sizes: ${DOCUMENT_SIZES.join(", ")})
- webpage: Websites with header/footer support (size: fluid)
- social: Social media posts (sizes: ${SOCIAL_SIZES.join(", ")})

PARAMETERS:
- prompt (required): Your content or instructions. Can be brief ("Company overview presentation") or detailed with bullet points.
- format (required): One of ${GAMMA_FORMATS.join(", ")}
- cards: Number of slides/sections (1-60, default: AI-determined)
- size: Aspect ratio appropriate for the format
- themeId: Visual theme ID (use gamma_list_themes to see options)
- language: Target language code (en, es, fr, de, zh, ja, etc.)
- imageStyle: ${IMAGE_STYLES.join(", ")}
- cardDensity: ${CARD_DENSITY.join(", ")}
- waitForCompletion: If true, waits up to 5 min for generation to complete

RETURNS:
- generationId: ID for tracking/status checks
- status: pending, completed, or failed
- url: Link to view content (when completed)
- title: Generated or custom title

EXAMPLES:
1. Quick presentation: { prompt: "5 slide pitch deck for AI startup", format: "presentation" }
2. Detailed document: { prompt: "Technical documentation for REST API...", format: "document", cards: 10 }
3. Styled content: { prompt: "Company culture overview", format: "presentation", themeId: "theme_123", waitForCompletion: true }

CREDITS: Each generation consumes Gamma API credits based on complexity.`,
      inputSchema: GenerateInputSchema,
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: true,
      },
    },
    async (params: GenerateInput) => {
      try {
        // Start generation
        const response = await client.generate({
          input: params.prompt,
          format: params.format,
          cards: params.cards,
          size: params.size as GammaSize | undefined,
          themeId: params.themeId,
          language: params.language,
          folderId: params.folderId,
          imageStyle: params.imageStyle,
          cardDensity: params.cardDensity,
          title: params.title,
        });

        // If waitForCompletion is true, poll until done
        if (params.waitForCompletion) {
          const finalStatus = await client.waitForCompletion(response.generationId);
          const formatted = formatGenerationOutput(finalStatus, params.response_format);
          return {
            content: [{ type: "text" as const, text: formatted.text }],
          };
        }

        // Return immediate response with pending status
        const formatted = formatGenerationOutput(
          {
            generationId: response.generationId,
            status: response.status,
          },
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
              text: `Error generating content: ${error instanceof Error ? error.message : String(error)}`,
            },
          ],
        };
      }
    }
  );

  // ============================================================================
  // gamma_get_status - Check generation progress
  // ============================================================================
  server.registerTool(
    "gamma_get_status",
    {
      title: "Get Generation Status",
      description: `Check the status of a Gamma generation.

Use this tool to check if a previously started generation has completed. Generations typically take 30 seconds to 2 minutes depending on complexity.

PARAMETERS:
- generationId (required): The ID returned from gamma_generate
- waitForCompletion: If true, polls until complete (max 5 minutes)

RETURNS:
- status: pending, completed, or failed
- url: Link to view content (when completed)
- title: Content title
- creditsUsed: Credits consumed

EXAMPLE:
{ generationId: "gen_abc123", waitForCompletion: true }`,
      inputSchema: GetStatusInputSchema,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: true,
      },
    },
    async (params: GetStatusInput) => {
      try {
        let status;

        if (params.waitForCompletion) {
          status = await client.waitForCompletion(params.generationId);
        } else {
          status = await client.getStatus(params.generationId);
        }

        const formatted = formatGenerationOutput(status, params.response_format);

        return {
          content: [{ type: "text" as const, text: formatted.text }],
        };
      } catch (error) {
        return {
          content: [
            {
              type: "text" as const,
              text: `Error checking status: ${error instanceof Error ? error.message : String(error)}`,
            },
          ],
        };
      }
    }
  );

  // ============================================================================
  // gamma_from_template - Remix existing content
  // ============================================================================
  server.registerTool(
    "gamma_from_template",
    {
      title: "Create from Template",
      description: `Create new content by remixing an existing Gamma template.

This tool uses Gamma's Remix feature to create a new version of existing content with customizations. Useful for creating variations of proven templates.

PARAMETERS:
- templateId (required): ID of the existing Gamma to use as template
- prompt: Additional instructions for customization
- variables: Key-value pairs for dynamic content substitution
- folderId: Folder to save the result
- waitForCompletion: If true, waits for completion

RETURNS:
Same as gamma_generate

EXAMPLE:
{
  templateId: "gamma_xyz789",
  prompt: "Update for Q1 2025 results",
  variables: { "company_name": "Acme Corp", "quarter": "Q1 2025" }
}`,
      inputSchema: FromTemplateInputSchema,
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: true,
      },
    },
    async (params: FromTemplateInput) => {
      try {
        const response = await client.createFromTemplate({
          templateId: params.templateId,
          prompt: params.prompt,
          variables: params.variables,
          folderId: params.folderId,
        });

        if (params.waitForCompletion) {
          const finalStatus = await client.waitForCompletion(response.generationId);
          const formatted = formatGenerationOutput(finalStatus, params.response_format);
          return {
            content: [{ type: "text" as const, text: formatted.text }],
          };
        }

        const formatted = formatGenerationOutput(
          {
            generationId: response.generationId,
            status: response.status,
          },
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
              text: `Error creating from template: ${error instanceof Error ? error.message : String(error)}`,
            },
          ],
        };
      }
    }
  );
}
