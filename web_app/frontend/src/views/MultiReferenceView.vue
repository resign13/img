<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { storeToRefs } from "pinia";

import { runMultiReferenceApi } from "@/api/client";
import FileUploadField from "@/components/FileUploadField.vue";
import ImagePreviewModal from "@/components/ImagePreviewModal.vue";
import { useAppStore } from "@/stores/app";
import { useWorkspaceStore } from "@/stores/workspace";
import type { MultiReferenceTask, NoticeMessage, UploadItem } from "@/types";
import { getErrorMessage } from "@/utils/errors";
import { createFileFromUrl } from "@/utils/files";

const appStore = useAppStore();
const workspaceStore = useWorkspaceStore();
const { multiReference } = storeToRefs(workspaceStore);

const referenceFiles = computed<UploadItem[]>({
  get: () => multiReference.value.referenceFiles,
  set: (value) => {
    multiReference.value.referenceFiles = value;
  },
});

const prompt = computed<string>({
  get: () => multiReference.value.prompt,
  set: (value) => {
    multiReference.value.prompt = value;
  },
});

const ratioLabel = computed<string>({
  get: () => multiReference.value.ratioLabel,
  set: (value) => {
    multiReference.value.ratioLabel = value;
  },
});

const tasks = computed<MultiReferenceTask[]>({
  get: () => multiReference.value.tasks,
  set: (value) => {
    multiReference.value.tasks = value;
  },
});

const notice = computed<NoticeMessage | null>({
  get: () => multiReference.value.notice,
  set: (value) => {
    multiReference.value.notice = value;
  },
});

const submitting = ref(false);
const previewImageUrl = ref("");
const previewImageTitle = ref("");

const ratioOptions = computed(() => {
  const all = appStore.publicConfig?.ratio_options ?? [];
  const currentModel = appStore.currentModel;
  if (!currentModel?.supports_ratio_selection || !currentModel.allowed_ratios.length) {
    return all;
  }
  return all.filter((item) => currentModel.allowed_ratios.includes(item.value));
});

const supportsTextOnlyGeneration = computed(() => Boolean(appStore.currentModel?.supports_text_only_generation));

watch(
  () => appStore.publicConfig,
  (config) => {
    if (config && !ratioLabel.value) {
      ratioLabel.value = config.defaults.ratio || ratioOptions.value[0]?.label || "";
    }
  },
  { immediate: true },
);

watch(
  ratioOptions,
  (options) => {
    if (options.length && !options.some((item) => item.label === ratioLabel.value)) {
      ratioLabel.value = options[0].label;
    }
  },
  { immediate: true },
);

function clearTasks() {
  tasks.value = [];
  appStore.addLog("多参考图任务列表已清空。");
}

function removeTask(id: string) {
  tasks.value = tasks.value.filter((item) => item.id !== id);
}

function openPreview(url: string, title: string) {
  previewImageUrl.value = url;
  previewImageTitle.value = title;
}

function closePreview() {
  previewImageUrl.value = "";
  previewImageTitle.value = "";
}

function startGenerate() {
  if (submitting.value) {
    return;
  }

  if (!referenceFiles.value.length && !supportsTextOnlyGeneration.value) {
    notice.value = { type: "error", message: `${appStore.imageModel} 需要至少上传 1 张参考图。` };
    return;
  }

  if (!prompt.value.trim()) {
    notice.value = { type: "error", message: "请输入提示词。" };
    return;
  }

  submitting.value = true;
  notice.value = null;

  try {
    const taskId = crypto.randomUUID();
    const taskPrompt = prompt.value.trim();
    const taskReferenceFiles = referenceFiles.value.map((item) => item.file);
    const taskRatioLabel = ratioLabel.value;
    const taskSettings = appStore.buildCommonSettings(taskRatioLabel);

    tasks.value = [
      {
        id: taskId,
        prompt: taskPrompt,
        status: "running",
        referenceFiles: taskReferenceFiles,
        ratioLabel: taskRatioLabel,
      },
      ...tasks.value,
    ];

    appStore.addLog(`多参考图任务已提交，参考图 ${taskReferenceFiles.length} 张。`);
    void runSubmittedTask(taskId, taskReferenceFiles, taskPrompt, taskSettings);
  } finally {
    submitting.value = false;
  }
}

async function runSubmittedTask(
  taskId: string,
  taskReferenceFiles: File[],
  taskPrompt: string,
  taskSettings: ReturnType<typeof appStore.buildCommonSettings>,
) {
  try {
    const response = await runMultiReferenceApi(taskReferenceFiles, taskPrompt, taskSettings);
    if (!response.ok) {
      throw new Error(response.message || "多参考图生成失败。");
    }

    tasks.value = tasks.value.map((item) =>
      item.id === taskId
        ? {
            ...item,
            status: "success",
            result: response.data,
          }
        : item,
    );
    appStore.addSuccessCount(1);
    appStore.addLog("多参考图生图任务已完成。");
    notice.value = { type: "success", message: "多参考图生图已完成。" };
  } catch (error) {
    const message = getErrorMessage(error);
    tasks.value = tasks.value.map((item) =>
      item.id === taskId
        ? {
            ...item,
            status: "error",
            error: message,
          }
        : item,
    );
    appStore.addLog(message, "ERROR");
    notice.value = { type: "error", message };
  }
}

async function redrawTask(task: MultiReferenceTask, useResultImage = false) {
  if (!task.prompt.trim()) {
    notice.value = { type: "error", message: "该任务没有可重绘的提示词。" };
    return;
  }

  if (!task.referenceFiles.length && !useResultImage && !supportsTextOnlyGeneration.value) {
    notice.value = { type: "error", message: "当前任务缺少参考图，无法重绘。" };
    return;
  }

  if (useResultImage && !task.result) {
    notice.value = { type: "error", message: "当前任务还没有结果图，无法进行结果重绘。" };
    return;
  }

  task.status = "running";
  task.error = undefined;
  notice.value = null;

  try {
    const sourceFiles = useResultImage
      ? [await createFileFromUrl(task.result!.url, task.result?.file_name || `${task.id}.png`)]
      : task.referenceFiles;

    const response = await runMultiReferenceApi(
      sourceFiles,
      task.prompt.trim(),
      appStore.buildCommonSettings(task.ratioLabel),
    );

    if (!response.ok) {
      throw new Error(response.message || "重绘失败。");
    }

    task.result = response.data;
    task.status = "success";
    appStore.addSuccessCount(1);
    appStore.addLog(useResultImage ? "多参考图结果重绘完成。" : "多参考图任务重绘完成。");
    notice.value = { type: "success", message: useResultImage ? "结果重绘完成。" : "重绘完成。" };
  } catch (error) {
    const message = getErrorMessage(error);
    task.status = "error";
    task.error = message;
    appStore.addLog(message, "ERROR");
    notice.value = { type: "error", message };
  }
}

function taskStatusText(status: MultiReferenceTask["status"]) {
  if (status === "success") return "已完成";
  if (status === "error") return "失败";
  return "执行中";
}

function taskStatusEnglish(status: MultiReferenceTask["status"]) {
  if (status === "success") return "Done";
  if (status === "error") return "Error";
  return "Running";
}
</script>

<template>
  <div class="desktop-module-grid multi-reference-layout">
    <section class="module-panel module-panel-left compact-panel">
      <div class="module-title-bar">
        <span>多参考图生图</span>
        <button class="mini-red-button compact-top" type="button" @click="clearTasks()">清空列表</button>
      </div>

      <div class="module-panel-body compact compact-panel-body multi-reference-form-body">
        <FileUploadField
          v-model="referenceFiles"
          title="1. 参考图"
          button-text="批量上传参考图"
          empty-text="未上传参考图，可点击或拖拽图片到这里批量上传"
          accent-class="accent-blue"
          compact
        />

        <label class="form-field">
          <span>2. 提示词</span>
          <textarea
            v-model="prompt"
            class="desktop-textarea medium"
            :placeholder="
              supportsTextOnlyGeneration
                ? '可只输入提示词进行文生图，也可以上传多张参考图融合生成。'
                : '输入提示词，系统会结合左侧多张参考图一起生成。'
            "
          ></textarea>
        </label>

        <label class="form-field">
          <span>3. 画面比例</span>
          <select v-model="ratioLabel" class="desktop-select" :disabled="!appStore.currentModel?.supports_ratio_selection">
            <option v-for="item in ratioOptions" :key="item.label" :value="item.label">
              {{ item.label }}
            </option>
          </select>
        </label>

        <div class="multi-reference-action-dock">
          <button
            class="module-main-button green compact-main-button"
            type="button"
            :disabled="submitting"
            @click="startGenerate()"
          >
            {{ submitting ? "提交中..." : "开始生成" }}
          </button>

          <div v-if="notice" class="notice-banner" :class="notice.type === 'error' ? 'notice-error' : 'notice-success'">
            {{ notice.message }}
          </div>
        </div>
      </div>
    </section>

    <section class="queue-shell">
      <div class="queue-header">
        <span>多参考图任务队列</span>
        <span class="queue-count">{{ tasks.length }}</span>
      </div>

      <div v-if="!tasks.length" class="queue-empty">点击开始生成后，任务会自动出现在这里并开始执行</div>

      <div v-else class="result-list">
        <article v-for="(task, index) in tasks" :key="task.id" class="scene-task-card">
          <div class="task-thumb-frame">
            <button
              v-if="task.result"
              class="task-thumb-button"
              type="button"
              @click="openPreview(task.result.url, task.result.title || `任务 ${index + 1}`)"
            >
              <img :src="task.result.url" :alt="task.result.title" class="task-thumb-image" />
            </button>
            <div v-else class="task-thumb-placeholder">
              <div class="task-thumb-status">{{ taskStatusEnglish(task.status) }}</div>
              <div class="task-thumb-substatus">{{ taskStatusText(task.status) }}</div>
            </div>
          </div>

          <div class="task-index-column">
            <div class="task-index-label">#{{ index + 1 }}</div>
            <div class="task-index-status">{{ taskStatusText(task.status) }}</div>
          </div>

          <div class="scene-task-main">
            <textarea v-model="task.prompt" class="desktop-textarea task task-prompt-box" placeholder="输入提示词..." />
            <div v-if="task.error" class="task-error-text">{{ task.error }}</div>
          </div>

          <div class="task-action-column">
            <button class="mini-blue-button compact" type="button" :disabled="task.status === 'running'" @click="redrawTask(task)">
              重绘
            </button>
            <button
              class="mini-indigo-button compact"
              type="button"
              :disabled="!task.result || task.status === 'running'"
              @click="redrawTask(task, true)"
            >
              结果重绘
            </button>
            <div class="task-icon-actions">
              <a
                v-if="task.result"
                class="icon-action-button"
                :href="task.result.url"
                :download="task.result.file_name || task.result.title"
                title="下载图片"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true" class="icon-action-svg">
                  <path d="M12 3v10m0 0 4-4m-4 4-4-4M5 17v2h14v-2" />
                </svg>
              </a>
              <button class="task-close-button compact" type="button" @click="removeTask(task.id)">×</button>
            </div>
          </div>
        </article>
      </div>
    </section>
  </div>

  <ImagePreviewModal
    v-if="previewImageUrl"
    :image-url="previewImageUrl"
    :title="previewImageTitle"
    @close="closePreview"
  />
</template>
