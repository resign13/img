<script setup lang="ts">
import { computed, ref } from "vue";

import type { UploadItem } from "@/types";
import { createUploadItems, revokeUploadItems } from "@/utils/files";

const props = withDefaults(
  defineProps<{
    modelValue: UploadItem[];
    title: string;
    buttonText: string;
    emptyText: string;
    multiple?: boolean;
    accentClass?: string;
    compact?: boolean;
    hidePreview?: boolean;
  }>(),
  {
    multiple: true,
    accentClass: "accent-blue",
    compact: false,
    hidePreview: false,
  },
);

const emit = defineEmits<{
  "update:modelValue": [value: UploadItem[]];
}>();

const fileInputRef = ref<HTMLInputElement | null>(null);
const dragDepth = ref(0);
const isDragging = computed(() => dragDepth.value > 0);

function openPicker() {
  fileInputRef.value?.click();
}

function appendFiles(files: FileList | File[]) {
  const imageFiles = Array.from(files).filter((file) => file.type.startsWith("image/"));
  if (!imageFiles.length) {
    return;
  }

  const nextItems = createUploadItems(imageFiles);
  if (!props.multiple) {
    revokeUploadItems(props.modelValue);
    emit("update:modelValue", nextItems.slice(0, 1));
  } else {
    emit("update:modelValue", [...props.modelValue, ...nextItems]);
  }
}

function onSelectFiles(event: Event) {
  const target = event.target as HTMLInputElement;
  if (!target.files?.length) {
    return;
  }

  appendFiles(target.files);
  target.value = "";
}

function clearFiles() {
  revokeUploadItems(props.modelValue);
  emit("update:modelValue", []);
}

function removeItem(id: string) {
  const matched = props.modelValue.find((item) => item.id === id);
  if (matched) {
    URL.revokeObjectURL(matched.previewUrl);
  }
  emit(
    "update:modelValue",
    props.modelValue.filter((item) => item.id !== id),
  );
}

function onDragEnter(event: DragEvent) {
  event.preventDefault();
  dragDepth.value += 1;
}

function onDragOver(event: DragEvent) {
  event.preventDefault();
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = "copy";
  }
}

function onDragLeave(event: DragEvent) {
  event.preventDefault();
  dragDepth.value = Math.max(0, dragDepth.value - 1);
}

function onDrop(event: DragEvent) {
  event.preventDefault();
  dragDepth.value = 0;
  if (event.dataTransfer?.files?.length) {
    appendFiles(event.dataTransfer.files);
  }
}
</script>

<template>
  <section class="upload-group" :class="{ compact }">
    <div class="upload-head" :class="{ compact }">
      <div class="upload-label">{{ title }}</div>
      <div class="upload-count">{{ modelValue.length }} 张</div>
    </div>

    <div class="upload-actions" :class="{ compact }">
      <button class="upload-button" :class="[accentClass, { compact }]" type="button" @click="openPicker()">
        {{ buttonText }}
      </button>
      <button class="upload-clear-button" :class="{ compact }" type="button" @click="clearFiles()">清空</button>
    </div>

    <input
      ref="fileInputRef"
      class="hidden-input"
      type="file"
      accept=".png,.jpg,.jpeg,.webp"
      :multiple="multiple"
      @change="onSelectFiles"
    />

    <div
      v-if="!hidePreview"
      class="upload-preview-shell"
      :class="[{ compact }, { 'is-dragging': isDragging }]"
      @click.self="openPicker()"
      @dragenter="onDragEnter"
      @dragover="onDragOver"
      @dragleave="onDragLeave"
      @drop="onDrop"
    >
      <div v-if="!modelValue.length" class="upload-empty">{{ emptyText }}</div>

      <div v-else class="upload-grid" :class="{ compact }">
        <div v-for="item in modelValue" :key="item.id" class="upload-card" :class="{ compact }">
          <button class="upload-remove-button" type="button" @click="removeItem(item.id)">×</button>
          <img :src="item.previewUrl" :alt="item.name" class="upload-thumb" :class="{ compact }" />
          <div class="upload-name" :class="{ compact }">{{ item.name }}</div>
        </div>
      </div>
    </div>
  </section>
</template>
