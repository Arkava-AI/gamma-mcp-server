/**
 * Gamma MCP Server Type Definitions
 *
 * TypeScript interfaces for Gamma API requests and responses.
 */

import {
  GAMMA_FORMATS,
  PRESENTATION_SIZES,
  DOCUMENT_SIZES,
  SOCIAL_SIZES,
  WEBPAGE_SIZES,
  IMAGE_STYLES,
  CARD_DENSITY,
} from "./constants.js";

// ============================================================================
// Utility Types
// ============================================================================

export type GammaFormat = (typeof GAMMA_FORMATS)[number];
export type PresentationSize = (typeof PRESENTATION_SIZES)[number];
export type DocumentSize = (typeof DOCUMENT_SIZES)[number];
export type SocialSize = (typeof SOCIAL_SIZES)[number];
export type WebpageSize = (typeof WEBPAGE_SIZES)[number];
export type ImageStyle = (typeof IMAGE_STYLES)[number];
export type CardDensity = (typeof CARD_DENSITY)[number];

// Size type varies by format
export type GammaSize = PresentationSize | DocumentSize | SocialSize | WebpageSize;

// ============================================================================
// API Request Types
// ============================================================================

/**
 * Request body for POST /v1.0/generations
 */
export interface GenerateRequest {
  /** The content prompt or messy notes to generate from */
  input: string;

  /** Type of content to generate */
  format: GammaFormat;

  /** Number of cards/slides to generate (1-60 for Pro, 1-75 for Ultra) */
  cards?: number;

  /** Size/aspect ratio - varies by format */
  size?: GammaSize;

  /** Theme ID from List Themes API */
  themeId?: string;

  /** Target language code (e.g., "en", "es", "fr") */
  language?: string;

  /** Folder ID to save the generation to */
  folderId?: string;

  /** AI image generation style */
  imageStyle?: ImageStyle;

  /** Card content density */
  cardDensity?: CardDensity;

  /** Custom title (overrides AI-generated title) */
  title?: string;

  /** For webpages: header content */
  headerContent?: string;

  /** For webpages: footer content */
  footerContent?: string;
}

/**
 * Request body for POST /v1.0/generations/from-template
 */
export interface CreateFromTemplateRequest {
  /** The template gamma ID to remix */
  templateId: string;

  /** Additional instructions for customization */
  prompt?: string;

  /** Variable substitutions for the template */
  variables?: Record<string, string>;

  /** Folder ID to save the generation to */
  folderId?: string;
}

/**
 * Pagination parameters for list endpoints
 */
export interface PaginationParams {
  /** Maximum items to return (1-100, default 20) */
  limit?: number;

  /** Number of items to skip */
  offset?: number;
}

// ============================================================================
// API Response Types
// ============================================================================

/**
 * Generation status values
 */
export type GenerationStatus = "pending" | "completed" | "failed";

/**
 * Response from POST /v1.0/generations
 */
export interface GenerateResponse {
  /** Unique generation ID for status polling */
  generationId: string;

  /** Current status */
  status: GenerationStatus;

  /** Estimated completion time in seconds (when pending) */
  estimatedSeconds?: number;
}

/**
 * Response from GET /v1.0/generations/{id}
 */
export interface GenerationStatusResponse {
  /** Unique generation ID */
  generationId: string;

  /** Current status */
  status: GenerationStatus;

  /** URL to view the generated content (when completed) */
  url?: string;

  /** Title of the generated content */
  title?: string;

  /** Error message (when failed) */
  error?: string;

  /** Credits consumed */
  creditsUsed?: number;
}

/**
 * Theme object from List Themes API
 */
export interface GammaTheme {
  /** Theme ID to use in generation requests */
  id: string;

  /** Display name of the theme */
  name: string;

  /** Theme description */
  description?: string;

  /** Preview image URL */
  thumbnailUrl?: string;

  /** Whether this is a custom user theme */
  isCustom?: boolean;
}

/**
 * Response from GET /v1.0/themes
 */
export interface ListThemesResponse {
  /** Array of available themes */
  themes: GammaTheme[];

  /** Total number of themes available */
  total: number;

  /** Whether more results are available */
  hasMore: boolean;
}

/**
 * Folder object from List Folders API
 */
export interface GammaFolder {
  /** Folder ID to use in generation requests */
  id: string;

  /** Folder name */
  name: string;

  /** Parent folder ID (null for root) */
  parentId?: string | null;

  /** Number of items in folder */
  itemCount?: number;
}

/**
 * Response from GET /v1.0/folders
 */
export interface ListFoldersResponse {
  /** Array of user folders */
  folders: GammaFolder[];

  /** Total number of folders */
  total: number;

  /** Whether more results are available */
  hasMore: boolean;
}

// ============================================================================
// MCP Tool Output Types
// ============================================================================

/**
 * Standardized output for list operations
 */
export interface PaginatedOutput<T> {
  /** Items in this response */
  items: T[];

  /** Total count of all items */
  total: number;

  /** Number of items in this response */
  count: number;

  /** Current offset */
  offset: number;

  /** Whether more items are available */
  hasMore: boolean;

  /** Offset for next page (if hasMore is true) */
  nextOffset?: number;
}

/**
 * Output for generation operations
 */
export interface GenerationOutput {
  /** Generation ID for tracking */
  generationId: string;

  /** Current status */
  status: GenerationStatus;

  /** URL to view content (when completed) */
  url?: string;

  /** Generated title */
  title?: string;

  /** Credits consumed */
  creditsUsed?: number;

  /** Message for user */
  message: string;
}

// ============================================================================
// Error Types
// ============================================================================

/**
 * Gamma API error response structure
 */
export interface GammaApiError {
  /** HTTP status code */
  status: number;

  /** Error message from API */
  message: string;

  /** Error code (e.g., "RATE_LIMITED", "INVALID_API_KEY") */
  code?: string;

  /** Additional details */
  details?: Record<string, unknown>;
}

/**
 * Response format enum for tool outputs
 */
export enum ResponseFormat {
  MARKDOWN = "markdown",
  JSON = "json",
}
