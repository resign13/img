<script setup lang="ts">
import { storeToRefs } from "pinia";
import { computed, ref, watch } from "vue";

import { generateSceneImagesApi, generateScenePromptsApi } from "@/api/client";
import FileUploadField from "@/components/FileUploadField.vue";
import ImagePreviewModal from "@/components/ImagePreviewModal.vue";
import { useAppStore } from "@/stores/app";
import { useWorkspaceStore } from "@/stores/workspace";
import type { NoticeMessage, ScenePromptItem, UploadItem } from "@/types";
import { getErrorMessage } from "@/utils/errors";
import { createFileFromUrl } from "@/utils/files";

const appStore = useAppStore();
const workspaceStore = useWorkspaceStore();
const { scene } = storeToRefs(workspaceStore);

const productFiles = computed<UploadItem[]>({
  get: () => scene.value.productFiles,
  set: (value) => {
    scene.value.productFiles = value;
  },
});

const promptItems = computed<ScenePromptItem[]>({
  get: () => scene.value.promptItems,
  set: (value) => {
    scene.value.promptItems = value;
  },
});

const styleName = computed<string>({
  get: () => scene.value.styleName,
  set: (value) => {
    scene.value.styleName = value;
  },
});

const templateName = computed<string>({
  get: () => scene.value.templateName,
  set: (value) => {
    scene.value.templateName = value;
  },
});

const ratioLabel = computed<string>({
  get: () => scene.value.ratioLabel,
  set: (value) => {
    scene.value.ratioLabel = value;
  },
});

const extraInfo = computed<string>({
  get: () => scene.value.extraInfo,
  set: (value) => {
    scene.value.extraInfo = value;
  },
});

const notice = computed<NoticeMessage | null>({
  get: () => scene.value.notice,
  set: (value) => {
    scene.value.notice = value;
  },
});

const generatingPrompts = ref(false);
const submittingImages = ref(false);
const previewImageUrl = ref("");
const previewImageTitle = ref("");

const styleKeys = computed(() => Object.keys(appStore.publicConfig?.styles ?? {}));
const templateKeys = computed(() => Object.keys(appStore.publicConfig?.templates ?? {}));
const ratioOptions = computed(() => {
  const all = appStore.publicConfig?.ratio_options ?? [];
  const currentModel = appStore.currentModel;
  if (!currentModel?.supports_ratio_selection || !currentModel.allowed_ratios.length) {
    return all;
  }
  return all.filter((item) => currentModel.allowed_ratios.includes(item.value));
});

watch(
  () => appStore.publicConfig,
  (config) => {
    if (!config) {
      return;
    }
    if (!styleName.value) {
      styleName.value = config.defaults.style || styleKeys.value[0] || "";
    }
    if (!templateName.value) {
      templateName.value = config.defaults.template || templateKeys.value[0] || "";
    }
    if (!ratioLabel.value) {
      ratioLabel.value = config.defaults.ratio || ratioOptions.value[0]?.label || "";
    }
    if (!extraInfo.value) {
      extraInfo.value = config.defaults.extra_info || "";
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

function setNotice(type: "success" | "error", message: string) {
  notice.value = { type, message };
}

function addPromptTask(text = "") {
  promptItems.value = [
    {
      id: crypto.randomUUID(),
      text,
      status: "waiting",
    },
    ...promptItems.value,
  ];
}

function clearPromptQueue() {
  promptItems.value = [];
  appStore.addLog("场景生图任务列表已清空。");
}

function openPreview(url: string, title: string) {
  previewImageUrl.value = url;
  previewImageTitle.value = title;
}

function closePreview() {
  previewImageUrl.value = "";
  previewImageTitle.value = "";
}

async function handleGeneratePrompts() {
  if (!productFiles.value.length) {
    setNotice("error", "请先上传产品图。");
    return;
  }

  generatingPrompts.value = true;
  notice.value = null;
  try {
    const response = await generateScenePromptsApi(
      productFiles.value[0].file,
      {
        templateName: templateName.value,
        styleName: styleName.value,
        styleDesc: appStore.publicConfig?.styles?.[styleName.value] ?? "",
        rawTemplate: appStore.publicConfig?.templates?.[templateName.value] ?? "",
        extraInfo: extraInfo.value,
      },
      appStore.buildCommonSettings(ratioLabel.value),
    );

    if (!response.ok) {
      throw new Error(response.message || "Prompt 生成失败。");
    }

    promptItems.value = response.data.map((text) => ({
      id: crypto.randomUUID(),
      text,
      status: "waiting" as const,
    }));
    appStore.addLog(`已生成 ${promptItems.value.length} 条场景 Prompt。`);
    setNotice("success", `Prompt 生成完成，共 ${promptItems.value.length} 条。`);
  } catch (error) {
    const message = getErrorMessage(error);
    appStore.addLog(message, "ERROR");
    setNotice("error", message);
  } finally {
    generatingPrompts.value = false;
  }
}

function handleGenerateImages() {
  if (submittingImages.value) {
    return;
  }
  if (!productFiles.value.length) {
    setNotice("error", "请先上传产品图。");
    return;
  }

  const submittedItems = promptItems.value.filter((item) => item.text.trim() && item.status !== "running");
  if (!submittedItems.length) {
    setNotice("error", "请先准备至少一条可生成的 Prompt。");
    return;
  }

  submittingImages.value = true;
  notice.value = null;

  try {
    const sourceFile = productFiles.value[0].file;
    const currentRatioLabel = ratioLabel.value;
    const submittedIds = new Set(submittedItems.map((item) => item.id));

    promptItems.value = promptItems.value.map((item) =>
      submittedIds.has(item.id)
        ? {
            ...item,
            status: "running",
            error: undefined,
            sourceFile,
            ratioLabel: currentRatioLabel,
          }
        : item,
    );

    appStore.addLog(`场景生图已提交 ${submittedItems.length} 个任务。`);
    setNotice("success", `已提交 ${submittedItems.length} 个场景生图任务，可继续提交新任务。`);

    for (const item of submittedItems) {
      void runSceneTask(item.id, item.text.trim(), sourceFile, currentRatioLabel);
    }
  } finally {
    submittingImages.value = false;
  }
}

async function runSceneTask(taskId: string, prompt: string, sourceFile: File, taskRatioLabel: string) {
  try {
    const response = await generateSceneImagesApi(sourceFile, [prompt], appStore.buildCommonSettings(taskRatioLabel));
    if (!response.ok || !response.data.length) {
      throw new Error(response.message || "场景图片生成失败。");
    }

    promptItems.value = promptItems.value.map((item) =>
      item.id === taskId
        ? {
            ...item,
            status: "success",
            result: response.data[0],
          }
        : item,
    );
    appStore.addSuccessCount(1);
    appStore.addLog("场景生图任务已完成。");
  } catch (error) {
    const message = getErrorMessage(error);
    promptItems.value = promptItems.value.map((item) =>
      item.id === taskId
        ? {
            ...item,
            status: "error",
            error: message,
          }
        : item,
    );
    appStore.addLog(message, "ERROR");
    setNotice("error", message);
  }
}

async function redrawTask(item: ScenePromptItem, useResultImage = false) {
  if (!item.text.trim()) {
    setNotice("error", "该任务没有可重绘的 Prompt。");
    return;
  }

  if (!productFiles.value.length && !item.sourceFile && !useResultImage) {
    setNotice("error", "请先上传产品图。");
    return;
  }

  if (useResultImage && !item.result) {
    setNotice("error", "当前任务还没有结果图，无法进行结果重绘。");
    return;
  }

  item.status = "running";
  item.error = undefined;
  notice.value = null;

  try {
    const sourceFile = useResultImage
      ? await createFileFromUrl(item.result!.url, item.result?.file_name || `${item.id}.png`)
      : item.sourceFile || productFiles.value[0].file;
    const taskRatioLabel = item.ratioLabel || ratioLabel.value;

    const response = await generateSceneImagesApi(
      sourceFile,
      [item.text.trim()],
      appStore.buildCommonSettings(taskRatioLabel),
    );

    if (!response.ok || !response.data.length) {
      throw new Error(response.message || "重绘失败。");
    }

    item.result = response.data[0];
    item.status = "success";
    item.sourceFile = sourceFile;
    item.ratioLabel = taskRatioLabel;
    appStore.addSuccessCount(1);
    appStore.addLog(useResultImage ? "场景任务结果重绘完成。" : "场景任务重绘完成。");
    setNotice("success", useResultImage ? "结果重绘完成。" : "重绘完成。");
  } catch (error) {
    const message = getErrorMessage(error);
    item.status = "error";
    item.error = message;
    appStore.addLog(message, "ERROR");
    setNotice("error", message);
  }
}

function removePromptItem(id: string) {
  promptItems.value = promptItems.value.filter((item) => item.id !== id);
}

function taskStatusText(status: ScenePromptItem["status"]) {
  if (status === "success") return "已完成";
  if (status === "error") return "失败";
  if (status === "running") return "执行中";
  return "待执行";
}

function taskStatusEnglish(status: ScenePromptItem["status"]) {
  if (status === "success") return "Done";
  if (status === "error") return "Error";
  if (status === "running") return "Running";
  return "Waiting";
}
</script>

<template>
  <div class="desktop-module-grid scene-layout">
    <section class="module-panel module-panel-left narrow">
      <div class="module-title-bar">
        <span>场景生图控制台</span>
      </div>

      <div class="module-panel-body compact">
        <FileUploadField
          v-model="productFiles"
          title="1. 产品图"
          button-text="上传产品图"
          empty-text="未上传产品图，可点击或拖拽图片到这里上传"
          :multiple="false"
          accent-class="accent-purple"
          :hide-preview="true"
        />

        <div class="single-preview-shell">
          <div v-if="productFiles[0]" class="single-preview-card">
            <img :src="productFiles[0].previewUrl" :alt="productFiles[0].name" class="single-preview-image" />
          </div>
          <div v-else class="upload-empty">这里显示当前产品图预览</div>
        </div>

        <div class="module-divider"></div>

        <div class="settings-title">生成设置</div>

        <label class="form-field">
          <span>视觉风格</span>
          <select v-model="styleName" class="desktop-select">
            <option v-for="item in styleKeys" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>

        <label class="form-field">
          <span>生成模板</span>
          <select v-model="templateName" class="desktop-select">
            <option v-for="item in templateKeys" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>

        <label class="form-field">
          <span>画面比例</span>
          <select v-model="ratioLabel" class="desktop-select" :disabled="!appStore.currentModel?.supports_ratio_selection">
            <option v-for="item in ratioOptions" :key="item.label" :value="item.label">
              {{ item.label }}
            </option>
          </select>
        </label>

        <label class="form-field">
          <span>补充要求</span>
          <textarea
            v-model="extraInfo"
            class="desktop-textarea compact"
            placeholder="补充卖点、材质、氛围、道具或镜头要求"
          ></textarea>
        </label>

        <div v-if="notice" class="notice-banner" :class="notice.type === 'error' ? 'notice-error' : 'notice-success'">
          {{ notice.message }}
        </div>

        <button
          class="module-main-button green scene-prompt-button"
          type="button"
          :disabled="generatingPrompts"
          @click="handleGeneratePrompts()"
        >
          {{ generatingPrompts ? "生成中..." : "生成 Prompt" }}
        </button>
      </div>
    </section>

    <section class="module-panel module-panel-right">
      <div class="scene-actions-row">
        <div class="task-count">任务 {{ promptItems.length }}</div>
        <div class="scene-action-buttons">
          <button class="mini-red-button" type="button" @click="clearPromptQueue()">清空列表</button>
          <button class="mini-teal-button" type="button" @click="addPromptTask()">手动任务</button>
          <button class="mini-green-button strong" type="button" :disabled="submittingImages" @click="handleGenerateImages()">
            {{ submittingImages ? "提交中..." : "批量生成" }}
          </button>
        </div>
      </div>

      <div class="queue-header">
        <span>任务列表</span>
        <span class="queue-count">{{ promptItems.length }}</span>
      </div>

      <div class="scene-task-list">
        <div v-if="!promptItems.length" class="queue-empty">这里会显示待生成或已完成的场景任务</div>

        <article v-for="(item, index) in promptItems" :key="item.id" class="scene-task-card">
          <div class="task-thumb-frame">
            <button
              v-if="item.result"
              class="task-thumb-button"
              type="button"
              @click="openPreview(item.result.url, item.result.title || `任务 ${index + 1}`)"
            >
              <img :src="item.result.url" :alt="item.result.title" class="task-thumb-image" />
            </button>
            <div v-else class="task-thumb-placeholder">
              <div class="task-thumb-status">{{ taskStatusEnglish(item.status) }}</div>
              <div class="task-thumb-substatus">{{ taskStatusText(item.status) }}</div>
            </div>
          </div>

          <div class="task-index-column">
            <div class="task-index-label">#{{ index + 1 }}</div>
            <div class="task-index-status">{{ taskStatusText(item.status) }}</div>
          </div>

          <div class="scene-task-main">
            <textarea v-model="item.text" class="desktop-textarea task task-prompt-box" placeholder="在这里输入 Prompt..." />
            <div v-if="item.error" class="task-error-text">{{ item.error }}</div>
          </div>

          <div class="task-action-column">
            <button class="mini-blue-button compact" type="button" :disabled="item.status === 'running'" @click="redrawTask(item)">
              重绘
            </button>
            <button
              class="mini-indigo-button compact"
              type="button"
              :disabled="!item.result || item.status === 'running'"
              @click="redrawTask(item, true)"
            >
              结果重绘
            </button>
            <div class="task-icon-actions">
              <a
                v-if="item.result"
                class="icon-action-button"
                :href="item.result.url"
                :download="item.result.file_name || item.result.title"
                title="下载图片"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true" class="icon-action-svg">
                  <path d="M12 3v10m0 0 4-4m-4 4-4-4M5 17v2h14v-2" />
                </svg>
              </a>
              <button class="task-close-button compact" type="button" @click="removePromptItem(item.id)">×</button>
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
