/**
 * Gamma MCP Server Constants
 *
 * Configuration values for the Gamma API integration.
 */

// API Configuration
export const GAMMA_API_BASE_URL = process.env.GAMMA_API_BASE_URL || "https://public-api.gamma.app/v1.0";
export const GAMMA_API_TIMEOUT = 60000; // 60 seconds for generation requests

// Response limits
export const CHARACTER_LIMIT = 25000;
export const DEFAULT_PAGE_LIMIT = 20;
export const MAX_PAGE_LIMIT = 100;
export const MAX_PROMPT_CHARS = 50000; // ~12,500 tokens — safe cap for prompts

// Generation limits
export const MAX_CARDS_PRO = 60;
export const MAX_CARDS_ULTRA = 75;
export const MAX_INPUT_TOKENS = 100000; // ~400,000 characters

// Polling configuration for generation status
export const POLL_INTERVAL_MS = 2000; // 2 seconds between status checks
export const MAX_POLL_ATTEMPTS = 150; // 5 minutes max wait (150 * 2s)

// Supported formats
export const GAMMA_FORMATS = ["presentation", "document", "webpage", "social"] as const;

// Presentation sizes
export const PRESENTATION_SIZES = ["fluid", "16x9", "4x3"] as const;

// Document sizes
export const DOCUMENT_SIZES = ["fluid", "pageless", "letter", "a4"] as const;

// Social post sizes
export const SOCIAL_SIZES = ["1x1", "4x5", "9x16"] as const;

// Webpage sizes
export const WEBPAGE_SIZES = ["fluid"] as const;

// Image styles for AI-generated images
export const IMAGE_STYLES = [
  "auto",
  "photographic",
  "generated",
  "clipart",
  "none"
] as const;

// Card density options
export const CARD_DENSITY = ["auto", "high", "low"] as const;

// Supported languages (partial list of 60+ languages)
export const SUPPORTED_LANGUAGES = [
  "en", "es", "fr", "de", "it", "pt", "nl", "ru", "zh", "ja",
  "ko", "ar", "hi", "tr", "pl", "sv", "da", "no", "fi", "cs"
] as const;

// Error messages
export const ERROR_MESSAGES = {
  MISSING_API_KEY: "GAMMA_API_KEY environment variable is required. Get your API key from https://gamma.app/settings",
  INVALID_API_KEY: "Invalid API key. Ensure you're using the X-API-KEY header format (not Bearer token). Keys start with 'sk-gamma-'",
  RATE_LIMITED: "Rate limit exceeded. Please wait before making more requests. Contact Gamma support for higher limits.",
  INSUFFICIENT_CREDITS: "Insufficient credits. Enable auto-recharge or upgrade your subscription at https://gamma.app/settings",
  GENERATION_TIMEOUT: "Generation timed out. The content may still be processing - check your Gamma dashboard.",
  GENERATION_FAILED: "Generation failed. Try simplifying your prompt or reducing the number of cards.",
  NETWORK_ERROR: "Network error connecting to Gamma API. Please check your internet connection.",
} as const;
