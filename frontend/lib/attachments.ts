// Mirrors the server's chat attachment rules so mistakes show before sending.
// The server stays authoritative.
const IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp", ".gif"];
const DOCUMENT_EXTENSIONS = [".pdf", ".docx", ".pptx", ".md", ".txt", ".csv"];

export const ATTACHMENT_ACCEPT = [...IMAGE_EXTENSIONS, ...DOCUMENT_EXTENSIONS].join(",");
export const MAX_ATTACHMENTS = 5;
export const MAX_ATTACHMENT_MB = 25;

function extension(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot === -1 ? "" : name.slice(dot).toLowerCase();
}

export function isImageFile(name: string): boolean {
  return IMAGE_EXTENSIONS.includes(extension(name));
}

export function addAttachments(
  pending: File[],
  incoming: File[],
): { files: File[]; error: string | null } {
  const files = [...pending];
  let error: string | null = null;
  for (const file of incoming) {
    if (![...IMAGE_EXTENSIONS, ...DOCUMENT_EXTENSIONS].includes(extension(file.name))) {
      error = `${file.name}: unsupported file type.`;
    } else if (file.size > MAX_ATTACHMENT_MB * 1024 * 1024) {
      error = `${file.name} is over the ${MAX_ATTACHMENT_MB}MB limit.`;
    } else if (files.length >= MAX_ATTACHMENTS) {
      error = `Attach at most ${MAX_ATTACHMENTS} files per message.`;
    } else {
      files.push(file);
    }
  }
  return { files, error };
}

// Pasted screenshots arrive unnamed ("image.png") or nameless; give them a usable name.
export function imagesFromClipboard(items: ArrayLike<{ kind: string; type: string; getAsFile(): File | null }>): File[] {
  const files: File[] = [];
  for (const item of Array.from(items)) {
    if (item.kind !== "file" || !item.type.startsWith("image/")) continue;
    const file = item.getAsFile();
    if (!file) continue;
    const ext = item.type.split("/")[1]?.replace("jpeg", "jpg") ?? "png";
    files.push(new File([file], file.name && file.name !== "image.png" ? file.name : `pasted-image.${ext}`, { type: item.type }));
  }
  return files;
}
