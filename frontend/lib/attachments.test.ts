import { describe, expect, it } from "vitest";
import { addAttachments, imagesFromClipboard, MAX_ATTACHMENTS } from "./attachments";

const file = (name: string, size = 10) => new File([new Uint8Array(size)], name);

describe("addAttachments", () => {
  it("accepts supported files", () => {
    const { files, error } = addAttachments([], [file("a.png"), file("b.pdf"), file("c.csv")]);
    expect(files.map((f) => f.name)).toEqual(["a.png", "b.pdf", "c.csv"]);
    expect(error).toBeNull();
  });

  it("rejects unsupported types, oversized files and more than the limit", () => {
    expect(addAttachments([], [file("virus.exe")]).error).toContain("unsupported");
    expect(addAttachments([], [file("big.pdf", 26 * 1024 * 1024)]).error).toContain("25MB");

    const full = Array.from({ length: MAX_ATTACHMENTS }, (_, i) => file(`${i}.txt`));
    const { files, error } = addAttachments(full, [file("extra.txt")]);
    expect(files).toHaveLength(MAX_ATTACHMENTS);
    expect(error).toContain("at most 5");
  });
});

describe("imagesFromClipboard", () => {
  it("names pasted screenshots and ignores pasted text", () => {
    const screenshot = new File(["x"], "image.png", { type: "image/png" });
    const files = imagesFromClipboard([
      { kind: "string", type: "text/plain", getAsFile: () => null },
      { kind: "file", type: "image/png", getAsFile: () => screenshot },
    ]);
    expect(files.map((f) => f.name)).toEqual(["pasted-image.png"]);
  });
});
