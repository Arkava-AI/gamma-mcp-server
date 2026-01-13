/**
 * Output Formatters
 *
 * Convert API responses to human-readable markdown or structured JSON.
 */

import {
  GenerationStatusResponse,
  GammaTheme,
  GammaFolder,
  PaginatedOutput,
  GenerationOutput,
} from "../types.js";

/**
 * Format generation output for display
 */
export function formatGenerationOutput(
  status: GenerationStatusResponse,
  format: "markdown" | "json"
): { text: string; structured: GenerationOutput } {
  const output: GenerationOutput = {
    generationId: status.generationId,
    status: status.status,
    url: status.url,
    title: status.title,
    creditsUsed: status.creditsUsed,
    message: getStatusMessage(status),
  };

  if (format === "json") {
    return {
      text: JSON.stringify(output, null, 2),
      structured: output,
    };
  }

  // Markdown format
  const lines: string[] = [];

  if (status.status === "completed") {
    lines.push(`# ✅ Generation Complete`);
    lines.push("");
    if (status.title) {
      lines.push(`**Title:** ${status.title}`);
    }
    if (status.url) {
      lines.push(`**View:** [Open in Gamma](${status.url})`);
    }
    if (status.creditsUsed) {
      lines.push(`**Credits Used:** ${status.creditsUsed}`);
    }
  } else if (status.status === "pending") {
    lines.push(`# ⏳ Generation In Progress`);
    lines.push("");
    lines.push(`**Generation ID:** \`${status.generationId}\``);
    lines.push("");
    lines.push(
      `Use \`gamma_get_status\` with this ID to check progress, or set \`waitForCompletion: true\` to wait automatically.`
    );
  } else if (status.status === "failed") {
    lines.push(`# ❌ Generation Failed`);
    lines.push("");
    lines.push(`**Error:** ${status.error || "Unknown error"}`);
    lines.push("");
    lines.push(`**Suggestions:**`);
    lines.push(`- Try simplifying your prompt`);
    lines.push(`- Reduce the number of cards`);
    lines.push(`- Check your Gamma dashboard for more details`);
  }

  lines.push("");
  lines.push(`---`);
  lines.push(`*Generation ID: ${status.generationId}*`);

  return {
    text: lines.join("\n"),
    structured: output,
  };
}

/**
 * Format themes list for display
 */
export function formatThemesOutput(
  themes: GammaTheme[],
  total: number,
  offset: number,
  format: "markdown" | "json"
): { text: string; structured: PaginatedOutput<GammaTheme> } {
  const output: PaginatedOutput<GammaTheme> = {
    items: themes,
    total,
    count: themes.length,
    offset,
    hasMore: total > offset + themes.length,
    ...(total > offset + themes.length && {
      nextOffset: offset + themes.length,
    }),
  };

  if (format === "json") {
    return {
      text: JSON.stringify(output, null, 2),
      structured: output,
    };
  }

  // Markdown format
  const lines: string[] = [
    `# 🎨 Available Themes`,
    "",
    `Showing ${themes.length} of ${total} themes${offset > 0 ? ` (offset: ${offset})` : ""}`,
    "",
  ];

  if (themes.length === 0) {
    lines.push("No themes found.");
  } else {
    for (const theme of themes) {
      lines.push(`## ${theme.name}`);
      lines.push(`- **ID:** \`${theme.id}\``);
      if (theme.description) {
        lines.push(`- **Description:** ${theme.description}`);
      }
      if (theme.isCustom) {
        lines.push(`- *Custom theme*`);
      }
      lines.push("");
    }
  }

  if (output.hasMore) {
    lines.push(`---`);
    lines.push(
      `*More themes available. Use \`offset: ${output.nextOffset}\` to see the next page.*`
    );
  }

  return {
    text: lines.join("\n"),
    structured: output,
  };
}

/**
 * Format folders list for display
 */
export function formatFoldersOutput(
  folders: GammaFolder[],
  total: number,
  offset: number,
  format: "markdown" | "json"
): { text: string; structured: PaginatedOutput<GammaFolder> } {
  const output: PaginatedOutput<GammaFolder> = {
    items: folders,
    total,
    count: folders.length,
    offset,
    hasMore: total > offset + folders.length,
    ...(total > offset + folders.length && {
      nextOffset: offset + folders.length,
    }),
  };

  if (format === "json") {
    return {
      text: JSON.stringify(output, null, 2),
      structured: output,
    };
  }

  // Markdown format
  const lines: string[] = [
    `# 📁 Your Folders`,
    "",
    `Showing ${folders.length} of ${total} folders${offset > 0 ? ` (offset: ${offset})` : ""}`,
    "",
  ];

  if (folders.length === 0) {
    lines.push("No folders found. Create folders in Gamma to organize your content.");
  } else {
    for (const folder of folders) {
      lines.push(`## ${folder.name}`);
      lines.push(`- **ID:** \`${folder.id}\``);
      if (folder.itemCount !== undefined) {
        lines.push(`- **Items:** ${folder.itemCount}`);
      }
      if (folder.parentId) {
        lines.push(`- **Parent:** \`${folder.parentId}\``);
      }
      lines.push("");
    }
  }

  if (output.hasMore) {
    lines.push(`---`);
    lines.push(
      `*More folders available. Use \`offset: ${output.nextOffset}\` to see the next page.*`
    );
  }

  return {
    text: lines.join("\n"),
    structured: output,
  };
}

/**
 * Format share result for display
 */
export function formatShareOutput(
  success: boolean,
  emails: string[],
  format: "markdown" | "json"
): { text: string; structured: { success: boolean; emails: string[] } } {
  const output = { success, emails };

  if (format === "json") {
    return {
      text: JSON.stringify(output, null, 2),
      structured: output,
    };
  }

  if (success) {
    return {
      text: `# ✅ Shared Successfully\n\nSent to:\n${emails.map((e) => `- ${e}`).join("\n")}`,
      structured: output,
    };
  }

  return {
    text: `# ❌ Share Failed\n\nCould not share with the specified emails. Please check the generation ID and try again.`,
    structured: output,
  };
}

/**
 * Get a user-friendly status message
 */
function getStatusMessage(status: GenerationStatusResponse): string {
  switch (status.status) {
    case "completed":
      return status.url
        ? `Generation complete! View your content at: ${status.url}`
        : "Generation complete!";
    case "pending":
      return "Generation is in progress. Use gamma_get_status to check progress.";
    case "failed":
      return status.error || "Generation failed. Please try again with a simpler prompt.";
    default:
      return `Status: ${status.status}`;
  }
}
