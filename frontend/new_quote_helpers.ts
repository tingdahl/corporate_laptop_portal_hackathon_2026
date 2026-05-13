export type UploadLike = {
  name: string;
  size: number;
  type: string;
};

export const SUPPORTED_UPLOAD_MIME_TYPES = [
  "image/png",
  "image/jpeg",
  "application/pdf",
] as const;

export function isSupportedUpload(file: UploadLike): boolean {
  return SUPPORTED_UPLOAD_MIME_TYPES.includes(file.type as (typeof SUPPORTED_UPLOAD_MIME_TYPES)[number]);
}

export function mergeUniqueUploads<T extends UploadLike>(existing: T[], incoming: T[]): T[] {
  const merged = [...existing];
  for (const file of incoming) {
    const duplicate = merged.find((f) => f.name === file.name && f.size === file.size);
    if (!duplicate) {
      merged.push(file);
    }
  }
  return merged;
}

export function shouldEnableInterpret(selectedCount: number): boolean {
  return selectedCount > 0;
}

export function formatSelectedFileList(files: UploadLike[]): string {
  return files
    .map((file, idx) => `<li key="${idx}">${file.name} (${(file.size / 1024).toFixed(1)} KB)</li>`)
    .join("");
}
