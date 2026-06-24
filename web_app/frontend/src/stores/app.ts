import { defineStore } from "pinia";

import { fetchPublicConfig } from "@/api/client";
import type { ModelConfig } from "@/types";

export const useAppStore = defineStore("app", {
  state: () => ({
    loading: false,
    initialized: false,
    publicConfig: null as Awaited<ReturnType<typeof fetchPublicConfig>> | null,
    logs: [] as string[],
    successCount: 0,
    imageModel: "",
    imageResolution: "",
    compressEnabled: false,
    compressTarget: 2,
  }),
  getters: {
    models(state): ModelConfig[] {
      return state.publicConfig?.models ?? [];
    },
    currentModel(state): ModelConfig | null {
      return state.publicConfig?.models.find((item) => item.label === state.imageModel) ?? null;
    },
    resolutionOptions(): string[] {
      return this.currentModel?.allowed_resolutions?.length
        ? this.currentModel.allowed_resolutions
        : this.publicConfig?.models[0]?.allowed_resolutions ?? [];
    },
  },
  actions: {
    async init() {
      if (this.initialized || this.loading) {
        return;
      }
      this.loading = true;
      try {
        this.publicConfig = await fetchPublicConfig();
        this.imageModel = this.publicConfig.defaults.image_model;
        this.imageResolution = this.publicConfig.defaults.image_resolution;
        this.compressEnabled = this.publicConfig.defaults.compress_enable;
        this.compressTarget = this.publicConfig.defaults.compress_target;
        this.addLog("网页端配置已加载。");
        this.initialized = true;
      } finally {
        this.loading = false;
      }
    },
    setImageModel(value: string) {
      this.imageModel = value;
      const currentModel = this.publicConfig?.models.find((item) => item.label === value);
      if (!currentModel) {
        return;
      }
      if (!currentModel.allowed_resolutions.includes(this.imageResolution)) {
        this.imageResolution = currentModel.allowed_resolutions[0] ?? this.imageResolution;
      }
    },
    addLog(message: string, level = "INFO") {
      const timeText = new Date().toLocaleTimeString("zh-CN", { hour12: false });
      this.logs.unshift(`[${timeText}] [${level}] ${message}`);
    },
    clearLogs() {
      this.logs = [];
    },
    addSuccessCount(value: number) {
      this.successCount += value;
    },
    buildCommonSettings(ratioLabel: string) {
      return {
        imageModel: this.imageModel,
        imageResolution: this.imageResolution,
        ratioLabel,
        compressEnabled: this.compressEnabled,
        compressTarget: this.compressTarget,
      };
    },
  },
});
