import { describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { renderToString } from "react-dom/server";
import { FileIcon, DocumentTable } from "./DocumentTable";
import { UploadDropzone } from "./UploadDropzone";

// Mock API
vi.mock("../lib/api", () => ({
  listDocuments: vi.fn().mockResolvedValue([
    {
      id: "doc-1",
      filename: "handbook.pdf",
      status: "ready",
      visibility: "company",
      createdAt: "2026-08-01T12:00:00Z",
    },
    {
      id: "doc-2",
      filename: "architecture.docx",
      status: "processing",
      visibility: "department",
      department: "Engineering",
      createdAt: "2026-08-02T12:00:00Z",
    },
    {
      id: "doc-3",
      filename: "presentation.pptx",
      status: "failed",
      errorMessage: "Parsing error: corrupted file",
      visibility: "company",
      createdAt: "2026-08-03T12:00:00Z",
    },
    {
      id: "doc-4",
      filename: "notes.md",
      status: "ready",
      visibility: "company",
      createdAt: "2026-08-04T12:00:00Z",
    },
  ]),
  deleteDocument: vi.fn().mockResolvedValue(undefined),
  uploadDocument: vi.fn().mockResolvedValue(undefined),
}));

describe("Knowledge Base Components", () => {
  describe("FileIcon", () => {
    it("renders PDF icon with red color and PDF label", () => {
      const html = renderToString(createElement(FileIcon, { filename: "manual.pdf" }));
      expect(html).toContain("#EF4444");
      expect(html).toContain("PDF");
    });

    it("renders DOCX icon with blue color and DOCX label", () => {
      const html = renderToString(createElement(FileIcon, { filename: "specs.docx" }));
      expect(html).toContain("#3B82F6");
      expect(html).toContain("DOCX");
    });

    it("renders PPTX icon with orange color and PPTX label", () => {
      const html = renderToString(createElement(FileIcon, { filename: "deck.pptx" }));
      expect(html).toContain("#F97316");
      expect(html).toContain("PPTX");
    });

    it("renders MD icon with gray color and MD label", () => {
      const html = renderToString(createElement(FileIcon, { filename: "readme.md" }));
      expect(html).toContain("#8B8B8E");
      expect(html).toContain("MD");
    });

    it("falls back to gray color for unknown extensions", () => {
      const html = renderToString(createElement(FileIcon, { filename: "data.xyz" }));
      expect(html).toContain("#8B8B8E");
      expect(html).toContain("XYZ");
    });
  });

  describe("UploadDropzone", () => {
    it("renders dropzone with rounded-xl, dashed border, and cloud upload icon", () => {
      const html = renderToString(createElement(UploadDropzone, { onUploaded: vi.fn() }));
      expect(html).toContain("rounded-xl");
      expect(html).toContain("border-dashed");
      expect(html).toContain("Drag and drop files here, or click to browse");
      expect(html).toContain("PDF, DOCX, PPTX, MD");
    });

    it("renders visibility selector styled for dark palette", () => {
      const html = renderToString(createElement(UploadDropzone, { onUploaded: vi.fn() }));
      expect(html).toContain("bg-surface-input");
      expect(html).toContain("Whole company");
      expect(html).toContain("My department only");
    });
  });

  describe("DocumentTable", () => {
    it("renders loading state on initial render", () => {
      const html = renderToString(createElement(DocumentTable, { refreshSignal: 0 }));
      expect(html).toContain("Loading…");
    });
  });
});
