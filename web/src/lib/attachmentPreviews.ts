const PREVIEW_IMAGE_MIME_TYPES = new Set(["image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"]);
const BASE64_PATTERN = /^[A-Za-z0-9+/]+={0,2}$/;

type AttachmentPreviewData = {
  mime_type?: string;
  base64?: string;
};

export function isPreviewableImageMime(mimeType: string | undefined) {
  return PREVIEW_IMAGE_MIME_TYPES.has((mimeType || "").toLowerCase());
}

export function getAttachmentPreviewDataUrl(attachment: AttachmentPreviewData) {
  const mimeType = (attachment.mime_type || "").toLowerCase();
  const base64 = attachment.base64 || "";
  if (!isPreviewableImageMime(mimeType) || !BASE64_PATTERN.test(base64)) {
    return "";
  }
  return `data:${mimeType};base64,${base64}`;
}
