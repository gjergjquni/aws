export const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png"] as const;

export const MAX_IMAGE_BYTES = 10 * 1024 * 1024;

const HEIC_TYPES = new Set([
  "image/heic",
  "image/heif",
  "image/heic-sequence",
  "image/heif-sequence",
]);

const EXT_TO_TYPE: Record<string, (typeof ALLOWED_IMAGE_TYPES)[number]> = {
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  png: "image/png",
};

const REJECTED_EXTENSIONS = new Set([
  "heic",
  "heif",
  "heics",
  "avif",
  "webp",
  "gif",
  "bmp",
  "tif",
  "tiff",
]);

export const EVIDENCE_FORMAT_ERROR = "Only JPEG and PNG images are supported.";

export type ValidatedEvidence = {
  contentType: (typeof ALLOWED_IMAGE_TYPES)[number];
};

function extensionOf(filename: string): string | null {
  const dot = filename.lastIndexOf(".");
  if (dot < 0 || dot === filename.length - 1) return null;
  return filename.slice(dot + 1).toLowerCase();
}

export function validateEvidenceFile(file: File): ValidatedEvidence {
  if (!file || file.size <= 0) {
    throw new Error("Image file is empty.");
  }
  if (file.size > MAX_IMAGE_BYTES) {
    throw new Error("Image exceeds the maximum size of 10 MB.");
  }

  const mime = (file.type || "").split(";")[0].trim().toLowerCase();
  const ext = extensionOf(file.name);

  if (HEIC_TYPES.has(mime) || ext === "heic" || ext === "heif" || ext === "heics") {
    throw new Error(EVIDENCE_FORMAT_ERROR);
  }
  if (ext && REJECTED_EXTENSIONS.has(ext)) {
    throw new Error(EVIDENCE_FORMAT_ERROR);
  }

  const mimeOk = mime === "image/jpeg" || mime === "image/png";
  const extType = ext ? EXT_TO_TYPE[ext] : undefined;

  if (mime && !mimeOk && mime !== "application/octet-stream") {
    throw new Error(EVIDENCE_FORMAT_ERROR);
  }
  if (mimeOk && extType && extType !== mime) {
    throw new Error(EVIDENCE_FORMAT_ERROR);
  }
  if (mimeOk) {
    return { contentType: mime };
  }
  if (extType) {
    return { contentType: extType };
  }
  throw new Error(EVIDENCE_FORMAT_ERROR);
}
