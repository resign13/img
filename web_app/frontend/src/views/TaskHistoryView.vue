<script setup lang="ts">
import { computed, onActivated, onMounted, ref } from "vue";

import { fetchHistoryImagesApi } from "@/api/client";
import ImagePreviewModal from "@/components/ImagePreviewModal.vue";
import type { HistoryImageItem } from "@/types";
import { getErrorMessage } from "@/utils/errors";

const images = ref<HistoryImageItem[]>([]);
const loading = ref(false);
const notice = ref<{ type: "success" | "error"; message: string } | null>(null);
const previewImageUrl = ref("");
const previewImageTitle = ref("");

const imageCountText = computed(() => `${images.value.length} 张`);

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
      <article v-for="(item, index) in images" :key="item.id" class="history-card">
        <div class="history-card-head">
          <div>
            <div class="history-card-title">#{{ images.length - index }} {{ item.title }}</div>
            <div class="history-time">{{ formatTime(item.created_at_text) }}</div>
          </div>
          <div class="history-card-actions">
            <button class="mini-blue-button compact" type="button" @click="openPreview(item)">查看</button>
            <a class="icon-action-button" :href="item.url" :download="item.file_name" title="下载图片">
              <svg viewBox="0 0 24 24" aria-hidden="true" class="icon-action-svg">
                <path d="M12 3v10m0 0 4-4m-4 4-4-4M5 17v2h14v-2" />
              </svg>
            </a>
          </div>
        </div>

        <button class="history-image-button" type="button" @click="openPreview(item)">
          <img :src="item.url" :alt="item.title" class="history-image" loading="lazy" />
        </button>

        <div class="history-card-body">
          <div class="history-meta-row">
            <span>{{ item.module_label }}</span>
            <span>会话 {{ item.session_label }}</span>
            <span v-if="item.source_name">{{ item.source_name }}</span>
            <span>{{ formatSize(item.size_bytes) }}</span>
          </div>

          <div class="history-footer-row">
            <a class="mini-blue-button history-open-link" :href="item.url" target="_blank" rel="noreferrer">打开原图</a>
            <a class="download-link history-download" :href="item.url" :download="item.file_name">下载图片</a>
          </div>
        </div>
      </article>
    </div>

    <div v-if="images.length" class="history-bottom-count">当前展示 {{ imageCountText }}历史图片</div>
  </section>

  <ImagePreviewModal
    v-if="previewImageUrl"
    :image-url="previewImageUrl"
    :title="previewImageTitle"
    @close="closePreview"
  />
</template>
