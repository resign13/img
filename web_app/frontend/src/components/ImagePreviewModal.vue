<script setup lang="ts">
defineProps<{
  imageUrl: string;
  title?: string;
}>();

const emit = defineEmits<{
  close: [];
}>();

function close() {
  emit("close");
}
</script>

<template>
  <Teleport to="body">
    <div class="image-modal-backdrop" @click.self="close">
      <div class="image-modal-shell">
        <div class="image-modal-header">
          <div class="image-modal-title">{{ title || "图片预览" }}</div>
          <button class="image-modal-close" type="button" @click="close">x</button>
        </div>
        <div class="image-modal-body">
          <img :src="imageUrl" :alt="title || 'preview'" class="image-modal-image" />
        </div>
      </div>
    </div>
  </Teleport>
</template>
