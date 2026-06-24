<script setup lang="ts">
import type { ResultItem } from "@/types";

defineProps<{
  title: string;
  results: ResultItem[];
  emptyText: string;
}>();
</script>

<template>
  <section class="queue-shell">
    <div class="queue-header">
      <span>{{ title }}</span>
      <span class="queue-count">{{ results.length }}</span>
    </div>

    <div v-if="!results.length" class="queue-empty">{{ emptyText }}</div>

    <div v-else class="result-list">
      <article v-for="(item, index) in results" :key="`${item.url}_${index}`" class="result-card">
        <div class="result-card-title">
          <div>
            <div class="result-main-title">#{{ index + 1 }} {{ item.title }}</div>
            <div v-if="item.source_name" class="result-subtitle">{{ item.source_name }}</div>
          </div>
          <div class="result-card-actions">
            <a class="mini-blue-button" :href="item.url" target="_blank" rel="noreferrer">查看结果</a>
            <a class="icon-action-button" :href="item.url" :download="item.file_name || item.title" title="下载图片">
              <svg viewBox="0 0 24 24" aria-hidden="true" class="icon-action-svg">
                <path d="M12 3v10m0 0 4-4m-4 4-4-4M5 17v2h14v-2" />
              </svg>
            </a>
          </div>
        </div>

        <img :src="item.url" :alt="item.title" class="result-image" />

        <details class="prompt-details">
          <summary>查看提示词</summary>
          <pre class="prompt-text">{{ item.prompt }}</pre>
        </details>

        <a class="download-link" :href="item.url" :download="item.file_name || item.title">下载图片</a>
      </article>
    </div>
  </section>
</template>
