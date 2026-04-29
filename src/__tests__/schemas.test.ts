import { describe, it } from "vitest";
import assert from "node:assert";
import {
  GenerateInputSchema,
  GetStatusInputSchema,
  FromTemplateInputSchema,
  ListThemesInputSchema,
  ListFoldersInputSchema,
  ShareEmailInputSchema,
} from "../schemas/index.js";

describe("GenerateInputSchema", () => {
  it("accepts valid minimal input", () => {
    const result = GenerateInputSchema.safeParse({
      prompt: "Test prompt",
      format: "presentation",
    });
    assert.ok(result.success, result.error?.message);
  });

  it("rejects missing prompt", () => {
    const result = GenerateInputSchema.safeParse({ format: "presentation" });
    assert.ok(!result.success);
  });

  it("rejects empty prompt", () => {
    const result = GenerateInputSchema.safeParse({ prompt: "", format: "presentation" });
    assert.ok(!result.success);
  });

  it("rejects prompt over 50000 chars", () => {
    const result = GenerateInputSchema.safeParse({
      prompt: "a".repeat(50001),
      format: "presentation",
    });
    assert.ok(!result.success);
  });

  it("accepts prompt at 50000 chars", () => {
    const result = GenerateInputSchema.safeParse({
      prompt: "a".repeat(50000),
      format: "presentation",
    });
    assert.ok(result.success);
  });

  it("rejects invalid format", () => {
    const result = GenerateInputSchema.safeParse({
      prompt: "Test",
      format: "video",
    });
    assert.ok(!result.success);
  });

  it("rejects headerContent over 2000 chars", () => {
    const result = GenerateInputSchema.safeParse({
      prompt: "Test",
      format: "webpage",
      headerContent: "a".repeat(2001),
    });
    assert.ok(!result.success);
  });

  it("rejects footerContent over 2000 chars", () => {
    const result = GenerateInputSchema.safeParse({
      prompt: "Test",
      format: "webpage",
      footerContent: "a".repeat(2001),
    });
    assert.ok(!result.success);
  });

  it("accepts all valid formats", () => {
    for (const format of ["presentation", "document", "webpage", "social"]) {
      const result = GenerateInputSchema.safeParse({ prompt: "Test", format });
      assert.ok(result.success, `Failed for ${format}: ${result.error?.message}`);
    }
  });

  it("rejects unknown fields via .strict()", () => {
    const result = GenerateInputSchema.safeParse({
      prompt: "Test",
      format: "presentation",
      unknownField: "value",
    });
    assert.ok(!result.success);
  });

  it("accepts size for presentation format", () => {
    const result = GenerateInputSchema.safeParse({
      prompt: "Test",
      format: "presentation",
      size: "16x9",
    });
    assert.ok(result.success);
  });

  it("rejects invalid size for presentation", () => {
    const result = GenerateInputSchema.safeParse({
      prompt: "Test",
      format: "presentation",
      size: "21x9",
    });
    assert.ok(!result.success);
  });

  it("accepts title up to 200 chars", () => {
    const result = GenerateInputSchema.safeParse({
      prompt: "Test",
      format: "presentation",
      title: "A".repeat(200),
    });
    assert.ok(result.success);
  });

  it("rejects title over 200 chars", () => {
    const result = GenerateInputSchema.safeParse({
      prompt: "Test",
      format: "presentation",
      title: "A".repeat(201),
    });
    assert.ok(!result.success);
  });
});

describe("GetStatusInputSchema", () => {
  it("accepts valid generationId", () => {
    const result = GetStatusInputSchema.safeParse({ generationId: "gen_abc123" });
    assert.ok(result.success);
  });

  it("rejects missing generationId", () => {
    const result = GetStatusInputSchema.safeParse({});
    assert.ok(!result.success);
  });

  it("rejects empty generationId", () => {
    const result = GetStatusInputSchema.safeParse({ generationId: "" });
    assert.ok(!result.success);
  });

  it("rejects unknown fields via .strict()", () => {
    const result = GetStatusInputSchema.safeParse({
      generationId: "gen_abc",
      unknown: "field",
    });
    assert.ok(!result.success);
  });
});

describe("FromTemplateInputSchema", () => {
  it("accepts valid templateId only", () => {
    const result = FromTemplateInputSchema.safeParse({ templateId: "gamma_xyz" });
    assert.ok(result.success);
  });

  it("rejects missing templateId", () => {
    const result = FromTemplateInputSchema.safeParse({ prompt: "Update" });
    assert.ok(!result.success);
  });

  it("accepts variables as record of strings", () => {
    const result = FromTemplateInputSchema.safeParse({
      templateId: "gamma_xyz",
      variables: { company_name: "Acme", quarter: "Q1" },
    });
    assert.ok(result.success);
  });

  it("rejects unknown fields via .strict()", () => {
    const result = FromTemplateInputSchema.safeParse({
      templateId: "gamma_xyz",
      unknown: "field",
    });
    assert.ok(!result.success);
  });
});

describe("ListThemesInputSchema", () => {
  it("accepts empty object (uses defaults)", () => {
    const result = ListThemesInputSchema.safeParse({});
    assert.ok(result.success);
  });

  it("accepts explicit limit and offset", () => {
    const result = ListThemesInputSchema.safeParse({ limit: 50, offset: 10 });
    assert.ok(result.success);
  });

  it("rejects limit over 100", () => {
    const result = ListThemesInputSchema.safeParse({ limit: 101 });
    assert.ok(!result.success);
  });

  it("rejects negative offset", () => {
    const result = ListThemesInputSchema.safeParse({ offset: -1 });
    assert.ok(!result.success);
  });
});

describe("ListFoldersInputSchema", () => {
  it("accepts empty object", () => {
    const result = ListFoldersInputSchema.safeParse({});
    assert.ok(result.success);
  });

  it("rejects limit over 100", () => {
    const result = ListFoldersInputSchema.safeParse({ limit: 101 });
    assert.ok(!result.success);
  });
});

describe("ShareEmailInputSchema", () => {
  it("accepts valid single email", () => {
    const result = ShareEmailInputSchema.safeParse({
      generationId: "gen_abc",
      emails: ["test@example.com"],
    });
    assert.ok(result.success);
  });

  it("accepts multiple emails", () => {
    const result = ShareEmailInputSchema.safeParse({
      generationId: "gen_abc",
      emails: ["a@example.com", "b@example.com"],
    });
    assert.ok(result.success);
  });

  it("rejects invalid email format", () => {
    const result = ShareEmailInputSchema.safeParse({
      generationId: "gen_abc",
      emails: ["not-an-email"],
    });
    assert.ok(!result.success);
  });

  it("rejects empty email array", () => {
    const result = ShareEmailInputSchema.safeParse({
      generationId: "gen_abc",
      emails: [],
    });
    assert.ok(!result.success);
  });

  it("rejects more than 10 emails", () => {
    const result = ShareEmailInputSchema.safeParse({
      generationId: "gen_abc",
      emails: Array(11).fill("test@example.com"),
    });
    assert.ok(!result.success);
  });

  it("rejects missing generationId", () => {
    const result = ShareEmailInputSchema.safeParse({
      emails: ["test@example.com"],
    });
    assert.ok(!result.success);
  });

  it("rejects message over 500 chars", () => {
    const result = ShareEmailInputSchema.safeParse({
      generationId: "gen_abc",
      emails: ["test@example.com"],
      message: "a".repeat(501),
    });
    assert.ok(!result.success);
  });
});
