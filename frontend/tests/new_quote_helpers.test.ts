import { describe, expect, it } from "vitest";
import {
  formatSelectedFileList,
  isSupportedUpload,
  mergeUniqueUploads,
  shouldEnableInterpret,
  type UploadLike,
} from "../new_quote_helpers";

describe("new_quote_helpers.ts", () => {
  it("accepts png/jpeg/pdf uploads and rejects unsupported types", () => {
    expect(isSupportedUpload({ name: "a.png", size: 10, type: "image/png" })).toBe(true);
    expect(isSupportedUpload({ name: "a.jpg", size: 10, type: "image/jpeg" })).toBe(true);
    expect(isSupportedUpload({ name: "a.pdf", size: 10, type: "application/pdf" })).toBe(true);
    expect(isSupportedUpload({ name: "a.txt", size: 10, type: "text/plain" })).toBe(false);
  });

  it("merges incoming files and removes duplicates by name+size", () => {
    const existing: UploadLike[] = [
      { name: "x.png", size: 100, type: "image/png" },
    ];
    const incoming: UploadLike[] = [
      { name: "x.png", size: 100, type: "image/png" },
      { name: "y.pdf", size: 250, type: "application/pdf" },
    ];

    const merged = mergeUniqueUploads(existing, incoming);

    expect(merged).toHaveLength(2);
    expect(merged[0].name).toBe("x.png");
    expect(merged[1].name).toBe("y.pdf");
  });

  it("enables interpret button when at least one file is selected", () => {
    expect(shouldEnableInterpret(0)).toBe(false);
    expect(shouldEnableInterpret(1)).toBe(true);
    expect(shouldEnableInterpret(3)).toBe(true);
  });

  it("formats selected files list html with KB values", () => {
    const html = formatSelectedFileList([
      { name: "x.png", size: 2048, type: "image/png" },
      { name: "y.pdf", size: 3072, type: "application/pdf" },
    ]);

    expect(html).toContain("x.png (2.0 KB)");
    expect(html).toContain("y.pdf (3.0 KB)");
    expect(html).toContain("<li");
  });
});
