<script setup lang="ts">
import { onActivated, onMounted, ref } from "vue";

import { fetchHistoryImagesApi } from "@/api/client";
import ImagePreviewModal from "@/components/ImagePreviewModal.vue";
import type { HistoryImageItem } from "@/types";
import { getErrorMessage } from "@/utils/errors";

const images = ref<HistoryImageItem[]>([]);
const loading = ref(false);
const notice = ref<{ type: "success" | "error"; message: string } | null>(null);
const previewImageUrl = ref("");
const previewImageTitle = ref("");

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

function openPreview(item: HistoryImageItem) {
  previewImageUrl.value = item.url;
  previewImageTitle.value = item.title || item.file_name;
}

function closePreview() {
  previewImageUrl.value = "";
  previewImageTitle.value = "";
}

async function loadHistory() {
  loading.value = true;
  notice.value = null;
  try {
    const response = await fetchHistoryImagesApi();
    if (!response.ok) {
      throw new Error(response.message || "历史记录加载失败。");
    }
    images.value = response.data;
    notice.value = { type: "success", message: `已加载 ${response.data.length} 张历史图片。` };
  } catch (error) {
    notice.value = { type: "error", message: getErrorMessage(error) };
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadHistory();
});

onActivated(() => {
  void loadHistory();
});
</script>

<template>
  <section class="module-panel history-page-panel">
    <div class="history-toolbar">
      <div>
        <div class="history-title">任务历史</div>
        <div class="history-subtitle">展示所有用户最近生成的图片；系统默认每 12 小时自动清理一次。</div>
      </div>
      <button class="mini-blue-button" type="button" :disabled="loading" @click="loadHistory()">
        {{ loading ? "刷新中" : "刷新历史" }}
      </button>
    </div>

    <div v-if="notice" class="notice-banner" :class="notice.type === 'error' ? 'notice-error' : 'notice-success'">
      {{ notice.message }}
    </div>

    <div v-if="!images.length && !loading" class="queue-empty history-empty">暂无历史生成图片</div>

    <div v-else class="history-grid">
      <article v-for="item in images" :key="item.id" class="history-card">
        <button class="history-image-button" type="button" @click="openPreview(item)">
          <img :src="item.url" :alt="item.title" class="history-image" loading="lazy" />
        </button>
        <div class="history-card-body">
          <div class="history-card-title">{{ item.title }}</div>
          <div class="history-meta-row">
            <span>{{ item.module_label }}</span>
            <span>会话 {{ item.session_label }}</span>
            <span>{{ formatSize(item.size_bytes) }}</span>
          </div>
          <div class="history-time">{{ formatTime(item.created_at_text) }}</div>
          <details v-if="item.prompt" class="prompt-details history-prompt">
            <summary>查看提示词</summary>
            <pre class="prompt-text">{{ item.prompt }}</pre>
          </details>
          <a class="download-link history-download" :href="item.url" :download="item.file_name">下载图片</a>
        </div>
      </article>
    </div>
  </section>

  <ImagePreviewModal
    v-if="previewImageUrl"
    :image-url="previewImageUrl"
    :title="previewImageTitle"
    @close="closePreview"
  />
</template>
