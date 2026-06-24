<script setup lang="ts">
defineProps<{
  title: string;
  description?: string;
}>();
</script>

<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <h3 class="panel-title">{{ title }}</h3>
        <p v-if="description" class="panel-desc">{{ description }}</p>
      </div>
    </div>
    <div class="uploader-placeholder">
      这里会放上传卡片、多图预览、任务列表和结果区。
    </div>
    <slot />
  </section>
</template>
