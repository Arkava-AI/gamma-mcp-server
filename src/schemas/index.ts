/**
 * Zod Validation Schemas for Gamma MCP Server
 *
 * Runtime input validation for all MCP tools.
 */

import { z } from "zod";
import {
  GAMMA_FORMATS,
  PRESENTATION_SIZES,
  DOCUMENT_SIZES,
  SOCIAL_SIZES,
  WEBPAGE_SIZES,
  IMAGE_STYLES,
  CARD_DENSITY,
  MAX_CARDS_PRO,
  DEFAULT_PAGE_LIMIT,
  MAX_PAGE_LIMIT,
} from "../constants.js";

// ============================================================================
// Common Schemas
// ============================================================================

/**
 * Response format option for tools
 */
export const ResponseFormatSchema = z
  .enum(["markdown", "json"])
  .default("markdown")
  .describe("Output format: 'markdown' for human-readable or 'json' for structured data");

/**
 * Pagination parameters
 */
export const PaginationSchema = z.object({
  limit: z
    .number()
    .int()
    .min(1)
    .max(MAX_PAGE_LIMIT)
    .default(DEFAULT_PAGE_LIMIT)
    .describe(`Maximum items to return (1-${MAX_PAGE_LIMIT}, default ${DEFAULT_PAGE_LIMIT})`),
  offset: z
    .number()
    .int()
    .min(0)
    .default(0)
    .describe("Number of items to skip for pagination"),
});

// ============================================================================
// Generation Schemas
// ============================================================================

/**
 * Schema for gamma_generate tool
 */
export const GenerateInputSchema = z
  .object({
    prompt: z
      .string()
      .min(1, "Prompt is required")
      .max(50000, "Prompt exceeds maximum length. Keep prompts under 50,000 characters (~12,500 tokens).")
      .describe(
        "The content to generate from. Can be a one-line prompt, messy notes, or polished content. Supports 60+ languages."
      ),

    format: z
      .enum(GAMMA_FORMATS)
      .describe(
        "Type of content to create: 'presentation' (slides), 'document' (report/article), 'webpage' (website), or 'social' (social media post)"
      ),

    cards: z
      .number()
      .int()
      .min(1)
      .max(MAX_CARDS_PRO)
      .optional()
      .describe(
        `Number of cards/slides to generate (1-${MAX_CARDS_PRO}). Defaults to AI-determined optimal count.`
      ),

    size: z
      .string()
      .optional()
      .describe(
        "Size/aspect ratio. Presentations: 'fluid', '16x9', '4x3'. Documents: 'fluid', 'pageless', 'letter', 'a4'. Social: '1x1', '4x5', '9x16'. Webpages: 'fluid'"
      ),

    themeId: z
      .string()
      .optional()
      .describe(
        "Theme ID for styling. Use gamma_list_themes to see available themes. Defaults to Gamma's default theme."
      ),

    language: z
      .string()
      .min(2)
      .max(10)
      .optional()
      .describe(
        "Target language code (e.g., 'en', 'es', 'fr', 'de', 'zh', 'ja'). Supports 60+ languages."
      ),

    folderId: z
      .string()
      .optional()
      .describe(
        "Folder ID to save the generation to. Use gamma_list_folders to see available folders."
      ),

    imageStyle: z
      .enum(IMAGE_STYLES)
      .optional()
      .describe(
        "AI image style: 'auto' (AI chooses), 'photographic', 'generated' (AI art), 'clipart', or 'none'"
      ),

    cardDensity: z
      .enum(CARD_DENSITY)
      .optional()
      .describe("Content density per card: 'auto', 'high' (more content), or 'low' (minimal)"),

    title: z
      .string()
      .max(200)
      .optional()
      .describe("Custom title. If not provided, Gamma AI generates one from the content."),

    headerContent: z
      .string()
      .max(2000)
      .optional()
      .describe("Custom header content for webpages."),
    
    footerContent: z
      .string()
      .max(2000)
      .optional()
      .describe("Custom footer content for webpages."),

    waitForCompletion: z
      .boolean()
      .default(false)
      .describe(
        "If true, poll until generation completes and return the final URL. If false, return immediately with generationId for manual status checking."
      ),

    response_format: ResponseFormatSchema,
  })
  .strict()
  .refine(
    (data) => {
      // Validate size matches format
      if (data.size) {
        const validSizes: Record<string, readonly string[]> = {
          presentation: PRESENTATION_SIZES,
          document: DOCUMENT_SIZES,
          social: SOCIAL_SIZES,
          webpage: WEBPAGE_SIZES,
        };
        const allowed = validSizes[data.format];
        if (allowed && !allowed.includes(data.size)) {
          return false;
        }
      }
      return true;
    },
    {
      message:
        "Invalid size for format. Use gamma_generate with response_format='json' to see valid sizes for each format.",
    }
  );

export type GenerateInput = z.infer<typeof GenerateInputSchema>;

/**
 * Schema for gamma_get_status tool
 */
export const GetStatusInputSchema = z
  .object({
    generationId: z
      .string()
      .min(1, "Generation ID is required")
      .describe("The generation ID returned from gamma_generate"),

    waitForCompletion: z
      .boolean()
      .default(false)
      .describe(
        "If true, poll until generation completes (up to 5 minutes). If false, return current status immediately."
      ),

    response_format: ResponseFormatSchema,
  })
  .strict();

export type GetStatusInput = z.infer<typeof GetStatusInputSchema>;

/**
 * Schema for gamma_from_template tool
 */
export const FromTemplateInputSchema = z
  .object({
    templateId: z
      .string()
      .min(1, "Template ID is required")
      .describe(
        "The ID of an existing Gamma to use as template. Find this in the Gamma URL or use gamma_list_folders to browse."
      ),

    prompt: z
      .string()
      .max(400000)
      .optional()
      .describe("Additional instructions for customizing the template content."),

    variables: z
      .record(z.string())
      .optional()
      .describe(
        "Key-value pairs to substitute in the template. Use for dynamic content like names, dates, or custom values."
      ),

    folderId: z
      .string()
      .optional()
      .describe("Folder ID to save the remixed version to."),

    waitForCompletion: z
      .boolean()
      .default(false)
      .describe("If true, poll until generation completes and return the final URL."),

    response_format: ResponseFormatSchema,
  })
  .strict();

export type FromTemplateInput = z.infer<typeof FromTemplateInputSchema>;

// ============================================================================
// List Schemas
// ============================================================================

/**
 * Schema for gamma_list_themes tool
 */
export const ListThemesInputSchema = z
  .object({
    limit: PaginationSchema.shape.limit,
    offset: PaginationSchema.shape.offset,
    response_format: ResponseFormatSchema,
  })
  .strict();

export type ListThemesInput = z.infer<typeof ListThemesInputSchema>;

/**
 * Schema for gamma_list_folders tool
 */
export const ListFoldersInputSchema = z
  .object({
    limit: PaginationSchema.shape.limit,
    offset: PaginationSchema.shape.offset,
    response_format: ResponseFormatSchema,
  })
  .strict();

export type ListFoldersInput = z.infer<typeof ListFoldersInputSchema>;

// ============================================================================
// Share Schema
// ============================================================================

/**
 * Schema for gamma_share_email tool
 */
export const ShareEmailInputSchema = z
  .object({
    generationId: z
      .string()
      .min(1, "Generation ID is required")
      .describe("The generation ID of the Gamma to share"),

    emails: z
      .array(z.string().email("Invalid email address"))
      .min(1, "At least one email is required")
      .max(10, "Maximum 10 emails per share request")
      .describe("List of email addresses to share with (max 10)"),

    message: z
      .string()
      .max(500)
      .optional()
      .describe("Optional personal message to include in the share email"),

    waitForCompletion: z
      .boolean()
      .optional()
      .describe("Wait for generation to complete before sharing (max 5 minutes)"),

    response_format: ResponseFormatSchema,
  })
  .strict();

export type ShareEmailInput = z.infer<typeof ShareEmailInputSchema>;

export const HealthInputSchema = z
  .object({
    response_format: ResponseFormatSchema,
  })
  .strict();

export type HealthInput = z.infer<typeof HealthInputSchema>;

export const ArchiveInputSchema = z
  .object({
    gammaId: z
      .string()
      .min(1, "Gamma ID is required")
      .describe("The ID of the Gamma to archive"),
    response_format: ResponseFormatSchema,
  })
  .strict();

export type ArchiveInput = z.infer<typeof ArchiveInputSchema>;
