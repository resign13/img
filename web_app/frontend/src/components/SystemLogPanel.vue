<script setup lang="ts">
import { storeToRefs } from "pinia";

import { useAppStore } from "@/stores/app";

const appStore = useAppStore();
const { logs } = storeToRefs(appStore);
</script>

<template>
  <section class="log-shell">
    <div class="log-header">
      <span>运行日志</span>
      <button class="mini-dark-button" type="button" @click="appStore.clearLogs()">清空</button>
    </div>
    <div class="log-body">
      <div v-if="!logs.length" class="log-empty">暂无日志</div>
      <pre v-else class="log-text">{{ logs.join("\n") }}</pre>
    </div>
  </section>
</template>
