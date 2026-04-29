/**
 * Gamma API Client
 *
 * HTTP client for Gamma API v1.0 with authentication, error handling, and polling.
 */

import axios, { AxiosError, AxiosInstance } from "axios";
import {
  GAMMA_API_BASE_URL,
  GAMMA_API_TIMEOUT,
  POLL_INTERVAL_MS,
  MAX_POLL_ATTEMPTS,
  ERROR_MESSAGES,
} from "../constants.js";
import {
  GenerateRequest,
  GenerateResponse,
  GenerationStatusResponse,
  CreateFromTemplateRequest,
  ListThemesResponse,
  ListFoldersResponse,
  GammaApiError,
  PaginationParams,
} from "../types.js";

/**
 * Gamma API Client class
 */
export class GammaClient {
  private readonly client: AxiosInstance;

  constructor(apiKey: string) {
    this.client = axios.create({
      baseURL: GAMMA_API_BASE_URL,
      timeout: GAMMA_API_TIMEOUT,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-API-KEY": apiKey,
      },
    });
  }

  /**
   * Generate a new Gamma (presentation, document, webpage, or social post)
   */
  async generate(request: GenerateRequest): Promise<GenerateResponse> {
    const response = await this.makeRequest<GenerateResponse>(
      "POST",
      "/generations",
      {
        input: request.input,
        format: request.format,
        ...(request.cards && { cards: request.cards }),
        ...(request.size && { size: request.size }),
        ...(request.themeId && { themeId: request.themeId }),
        ...(request.language && { language: request.language }),
        ...(request.folderId && { folderId: request.folderId }),
        ...(request.imageStyle && { imageStyle: request.imageStyle }),
        ...(request.cardDensity && { cardDensity: request.cardDensity }),
        ...(request.title && { title: request.title }),
        ...(request.headerContent && { headerContent: request.headerContent }),
        ...(request.footerContent && { footerContent: request.footerContent }),
      }
    );
    return response;
  }

  /**
   * Get the status of a generation
   */
  async getStatus(generationId: string): Promise<GenerationStatusResponse> {
    return this.makeRequest<GenerationStatusResponse>(
      "GET",
      `/generations/${encodeURIComponent(generationId)}`
    );
  }

  /**
   * Poll for generation completion
   */
  async waitForCompletion(
    generationId: string,
    maxAttempts: number = MAX_POLL_ATTEMPTS
  ): Promise<GenerationStatusResponse> {
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      const status = await this.getStatus(generationId);

      if (status.status === "completed" || status.status === "failed") {
        return status;
      }

      // Wait before next poll
      await this.sleep(POLL_INTERVAL_MS);
    }

    throw new Error(ERROR_MESSAGES.GENERATION_TIMEOUT);
  }

  /**
   * Create from an existing template (Remix)
   */
  async createFromTemplate(
    request: CreateFromTemplateRequest
  ): Promise<GenerateResponse> {
    return this.makeRequest<GenerateResponse>(
      "POST",
      "/generations/from-template",
      {
        templateId: request.templateId,
        ...(request.prompt && { prompt: request.prompt }),
        ...(request.variables && { variables: request.variables }),
        ...(request.folderId && { folderId: request.folderId }),
      }
    );
  }

  /**
   * List available themes
   */
  async listThemes(params?: PaginationParams): Promise<ListThemesResponse> {
    return this.makeRequest<ListThemesResponse>("GET", "/themes", undefined, {
      limit: params?.limit ?? 20,
      offset: params?.offset ?? 0,
    });
  }

  /**
   * List user folders
   */
  async listFolders(params?: PaginationParams): Promise<ListFoldersResponse> {
    return this.makeRequest<ListFoldersResponse>("GET", "/folders", undefined, {
      limit: params?.limit ?? 20,
      offset: params?.offset ?? 0,
    });
  }

  /**
   * Share a generation via email
   * Note: This endpoint may not be available in all API versions
   */
  async shareEmail(
    generationId: string,
    emails: string[],
    message?: string
  ): Promise<{ success: boolean; message: string }> {
    return this.makeRequest<{ success: boolean; message: string }>(
      "POST",
      `/generations/${encodeURIComponent(generationId)}/share`,
      {
        emails,
        ...(message && { message }),
      }
    );
  }

  // ============================================================================
  // Private Helpers
  // ============================================================================

  /**
   * Make an authenticated API request
   */
  private async makeRequest<T>(
    method: "GET" | "POST" | "PUT" | "DELETE",
    endpoint: string,
    data?: unknown,
    params?: Record<string, unknown>
  ): Promise<T> {
    try {
      const response = await this.client.request<T>({
        method,
        url: endpoint,
        data,
        params,
      });
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Convert API errors to user-friendly messages
   */
  private handleError(error: unknown): Error {
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError<GammaApiError>;

      if (axiosError.response) {
        const { status } = axiosError.response;

        switch (status) {
          case 401:
            return new Error(ERROR_MESSAGES.INVALID_API_KEY);
          case 403:
            return new Error(ERROR_MESSAGES.INSUFFICIENT_CREDITS);
          case 429:
            return new Error(ERROR_MESSAGES.RATE_LIMITED);
          case 404:
            return new Error(
              `Resource not found. Please verify the ID is correct.`
            );
          case 400:
            return new Error(
              "Invalid request. Check your parameters (format, size, themeId, etc.) and try again."
            );
          case 500:
          case 502:
          case 503:
            return new Error(
              `Gamma API is temporarily unavailable. Please try again in a few minutes.`
            );
          default:
            return new Error(
              `Gamma API error (${status}). Please try again or contact Gamma support if the issue persists.`
            );
        }
      }

      if (axiosError.code === "ECONNABORTED") {
        return new Error(
          "Request timed out. The generation may still be processing - use gamma_get_status to check."
        );
      }

      if (axiosError.code === "ENOTFOUND" || axiosError.code === "ECONNREFUSED") {
        return new Error(ERROR_MESSAGES.NETWORK_ERROR);
      }
    }

    return new Error(
      `Unexpected error: ${error instanceof Error ? error.message : String(error)}`
    );
  }

  /**
   * Sleep helper for polling
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

/**
 * Create a GammaClient instance from environment variables
 */
export function createGammaClient(): GammaClient {
  const apiKey = process.env.GAMMA_API_KEY;

  if (!apiKey) {
    throw new Error(ERROR_MESSAGES.MISSING_API_KEY);
  }

  if (!apiKey.startsWith("sk-gamma-")) {
    throw new Error(
      "Invalid API key format. Gamma API keys should start with 'sk-gamma-'. Check your GAMMA_API_KEY environment variable."
    );
  }

  return new GammaClient(apiKey);
}
