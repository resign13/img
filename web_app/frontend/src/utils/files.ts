import type { UploadItem } from "@/types";

let uploadCounter = 0;

export function createUploadItems(files: File[] | FileList): UploadItem[] {
  return Array.from(files).map((file) => ({
    id: `upload_${uploadCounter++}`,
    file,
    name: file.name,
    previewUrl: URL.createObjectURL(file),
  }));
}

export function revokeUploadItems(items: UploadItem[]) {
  items.forEach((item) => URL.revokeObjectURL(item.previewUrl));
}

export async function createFileFromUrl(url: string, fallbackName = "result.png"): Promise<File> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error("无法读取结果图用于重绘。");
  }

  const blob = await response.blob();
  const mimeType = blob.type || "image/png";
  const extension = mimeType.includes("jpeg") ? ".jpg" : mimeType.includes("webp") ? ".webp" : ".png";
  const safeName = /\.[a-z0-9]+$/i.test(fallbackName) ? fallbackName : `${fallbackName}${extension}`;

  return new File([blob], safeName, {
    type: mimeType,
  });
}
