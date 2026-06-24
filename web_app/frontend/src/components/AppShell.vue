<script setup lang="ts">
import { storeToRefs } from "pinia";

import SystemLogPanel from "@/components/SystemLogPanel.vue";
import { useAppStore } from "@/stores/app";

const appStore = useAppStore();
const { imageModel, imageResolution, compressEnabled, compressTarget, successCount } = storeToRefs(appStore);

function handleModelChange(event: Event) {
  const target = event.target as HTMLSelectElement;
  appStore.setImageModel(target.value);
}

function handleResolutionChange(event: Event) {
  const target = event.target as HTMLSelectElement;
  appStore.imageResolution = target.value;
}
</script>

<template>
  <div class="shell">
    <header class="desktop-topbar">
      <div class="toolbar-brand">AI BatchPic</div>

      <div class="toolbar-controls">
        <label class="toolbar-field">
          <span class="toolbar-label">模型</span>
          <select :value="imageModel" class="toolbar-select" @change="handleModelChange">
            <option v-for="model in appStore.models" :key="model.label" :value="model.label">
              {{ model.label }}
            </option>
          </select>
        </label>

        <label class="toolbar-field">
          <span class="toolbar-label">清晰度</span>
          <select
            :value="imageResolution"
            class="toolbar-select short"
            :disabled="!appStore.currentModel?.supports_resolution_selection"
            @change="handleResolutionChange"
          >
            <option v-for="item in appStore.resolutionOptions" :key="item" :value="item">
              {{ item }}
            </option>
          </select>
        </label>

        <label class="toolbar-checkbox">
          <input v-model="compressEnabled" type="checkbox" />
          <span>自动压缩</span>
        </label>

        <input v-model="compressTarget" class="toolbar-input toolbar-input-mini" type="number" min="0.5" step="0.5" />
        <span class="toolbar-unit">MB</span>

        <div class="success-counter">累计生成 {{ successCount }}</div>
      </div>
    </header>

    <div class="tabs-shell">
      <RouterLink class="desktop-tab" to="/scene">场景生图</RouterLink>
      <RouterLink class="desktop-tab" to="/replacer">爆款替换</RouterLink>
      <RouterLink class="desktop-tab" to="/multi-reference">多参考图生图</RouterLink>
      <RouterLink class="desktop-tab" to="/face-swap">批量换头</RouterLink>
      <RouterLink class="desktop-tab" to="/history">任务历史</RouterLink>
    </div>

    <main class="desktop-content">
      <slot />
    </main>

    <SystemLogPanel />
  </div>
</template>
