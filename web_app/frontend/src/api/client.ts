import axios from "axios";

import type { HistoryImagePage, PublicConfigResponse, ResultItem } from "@/types";

export const apiClient = axios.create({
  baseURL: "/api",
  timeout: 1200000,
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

export async function fetchHistoryImagesApi(limit = 12, offset = 0) {
  const { data } = await apiClient.get<{ ok: boolean; data: HistoryImagePage; message?: string }>("/history/images", {
    params: { limit, offset },
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

type MultiReferenceProgress = "queued" | "running" | "reconnecting";

export class TaskStatusUnknownError extends Error {}

export async function waitForMultiReferenceApi(taskId: string, onStatus: (status: MultiReferenceProgress, seconds: number) => void, submissionUnknown = false) {
  let missing = 0;
  let failures = 0;
  const started = Date.now();
  for (;;) {
    await new Promise((resolve) => setTimeout(resolve, 2500));
    try {
      const { data } = await apiClient.get<{ok: boolean; data: {status: "queued" | "running" | "success" | "error"; elapsed_seconds: number; result?: ResultItem; error?: string}}>(`/multi-reference/tasks/${taskId}`, {params: {session_id: getWebSessionId()}, timeout: 15000});
      missing = 0;
      failures = 0;
      submissionUnknown = false;
      if (data.data.status === "success" && data.data.result) return {ok: true, data: data.data.result};
      if (data.data.status === "error") throw new Error(data.data.error || "生图失败。");
      onStatus(data.data.status as "queued" | "running", data.data.elapsed_seconds);
    } catch (error: any) {
      if (!error?.isAxiosError) throw error;
      if (error?.response?.status === 404) {
        if (++missing >= 4) throw new TaskStatusUnknownError(submissionUnknown ? "提交状态无法确认，请先检查历史记录及平台账单，再决定是否重试。" : "任务不存在或服务器已重启，请先检查历史记录及平台账单，再决定是否重试。");
      }
      if (++failures >= 4) throw new TaskStatusUnknownError("暂时无法查询任务，可能仍在生成。请稍后重新查询并检查历史记录，避免重复提交。");
      onStatus("reconnecting", Math.floor((Date.now() - started) / 1000));
    }
  }
}

export async function runMultiReferenceApi(referenceFiles: File[], prompt: string, settings: CommonRequestSettings, taskId: string, onStatus: (status: MultiReferenceProgress, seconds: number) => void) {
  const formData = new FormData();
  referenceFiles.forEach((file) => formData.append("reference_images", file));
  formData.append("prompt", prompt);
  formData.append("task_id", taskId);
  appendCommonSettings(formData, settings);
  let submissionUnknown = false;
  try {
    await apiClient.post("/multi-reference/tasks", formData, { timeout: 30000 });
  } catch (error: any) {
    if (error?.response && error.response.status < 500) throw error;
    submissionUnknown = true;
    onStatus("reconnecting", 0);
  }
  return waitForMultiReferenceApi(taskId, onStatus, submissionUnknown);
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
