import axios from "axios";

import type { HistoryImageItem, PublicConfigResponse, ResultItem } from "@/types";

export const apiClient = axios.create({
  baseURL: "/api",
  timeout: 300000,
});

const SESSION_STORAGE_KEY = "ai-batchpic-web-session-id";

function createSessionId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

export function getWebSessionId() {
  let sessionId = localStorage.getItem(SESSION_STORAGE_KEY);
  if (!sessionId) {
    sessionId = createSessionId();
    localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  }
  return sessionId;
}

export async function fetchPublicConfig() {
  const { data } = await apiClient.get<{ ok: boolean; data: PublicConfigResponse }>("/config/public");
  return data.data;
}

export async function fetchHistoryImagesApi(limit = 300) {
  const { data } = await apiClient.get<{ ok: boolean; data: HistoryImageItem[]; message?: string }>("/history/images", {
    params: { limit },
  });
  return data;
}

export type CommonRequestSettings = {
  imageModel: string;
  imageResolution: string;
  ratioLabel: string;
  compressEnabled: boolean;
  compressTarget: number;
};

function appendCommonSettings(formData: FormData, settings: CommonRequestSettings) {
  formData.append("session_id", getWebSessionId());
  formData.append("image_model", settings.imageModel);
  formData.append("image_resolution", settings.imageResolution);
  formData.append("ratio_label", settings.ratioLabel);
  formData.append("compress_enabled", settings.compressEnabled ? "true" : "false");
  formData.append("compress_target", String(settings.compressTarget));
}

export async function analyzeSceneStyleApi(
  file: File,
  styleNames: string[],
  settings: CommonRequestSettings,
) {
  const formData = new FormData();
  formData.append("source_image", file);
  styleNames.forEach((styleName) => formData.append("style_names", styleName));
  appendCommonSettings(formData, settings);
  const { data } = await apiClient.post("/scene/analyze-style", formData);
  return data;
}

export async function generateScenePromptsApi(
  file: File,
  payload: {
    templateName: string;
    styleName: string;
    styleDesc: string;
    rawTemplate: string;
    extraInfo: string;
  },
  settings: CommonRequestSettings,
) {
  const formData = new FormData();
  formData.append("source_image", file);
  formData.append("template_name", payload.templateName);
  formData.append("style_name", payload.styleName);
  formData.append("style_desc", payload.styleDesc);
  formData.append("raw_template", payload.rawTemplate);
  formData.append("extra_info", payload.extraInfo);
  appendCommonSettings(formData, settings);
  const { data } = await apiClient.post<{ ok: boolean; data: string[]; message?: string }>("/scene/prompts", formData);
  return data;
}

export async function generateSceneImagesApi(file: File, prompts: string[], settings: CommonRequestSettings) {
  const formData = new FormData();
  formData.append("source_image", file);
  formData.append("prompts_json", JSON.stringify(prompts));
  appendCommonSettings(formData, settings);
  const { data } = await apiClient.post<{ ok: boolean; data: ResultItem[]; message?: string }>("/scene/generate", formData);
  return data;
}

export async function runReplacerApi(
  sceneFiles: File[],
  productFiles: File[],
  manualText: string,
  settings: CommonRequestSettings,
) {
  const formData = new FormData();
  sceneFiles.forEach((file) => formData.append("scene_images", file));
  productFiles.forEach((file) => formData.append("product_images", file));
  formData.append("manual_text", manualText);
  appendCommonSettings(formData, settings);
  const { data } = await apiClient.post<{ ok: boolean; data: ResultItem[]; message?: string }>("/replacer/run", formData);
  return data;
}

export async function runMultiReferenceApi(referenceFiles: File[], prompt: string, settings: CommonRequestSettings) {
  const formData = new FormData();
  referenceFiles.forEach((file) => formData.append("reference_images", file));
  formData.append("prompt", prompt);
  appendCommonSettings(formData, settings);
  const { data } = await apiClient.post<{ ok: boolean; data: ResultItem; message?: string }>("/multi-reference/run", formData);
  return data;
}

export async function runFaceSwapApi(
  targetFiles: File[],
  headFiles: File[],
  accessoryFiles: File[],
  manualText: string,
  settings: CommonRequestSettings,
) {
  const formData = new FormData();
  targetFiles.forEach((file) => formData.append("target_images", file));
  headFiles.forEach((file) => formData.append("head_images", file));
  accessoryFiles.forEach((file) => formData.append("accessory_images", file));
  formData.append("manual_text", manualText);
  appendCommonSettings(formData, settings);
  const { data } = await apiClient.post<{ ok: boolean; data: ResultItem[]; message?: string }>("/face-swap/run", formData);
  return data;
}
