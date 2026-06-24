<script setup lang="ts">
import { storeToRefs } from "pinia";
import { computed, ref, watch } from "vue";

import { runFaceSwapApi } from "@/api/client";
import FileUploadField from "@/components/FileUploadField.vue";
import ImagePreviewModal from "@/components/ImagePreviewModal.vue";
import { useAppStore } from "@/stores/app";
import { useWorkspaceStore } from "@/stores/workspace";
import type { FaceQueueTask, FaceTask } from "@/types";
import { getErrorMessage } from "@/utils/errors";
import { revokeUploadItems } from "@/utils/files";

const appStore = useAppStore();
const workspaceStore = useWorkspaceStore();
const { faceSwap } = storeToRefs(workspaceStore);

const tasks = computed({
  get: () => faceSwap.value.tasks,
  set: (value: FaceTask[]) => {
    faceSwap.value.tasks = value;
  },
});

const queueTasks = computed({
  get: () => faceSwap.value.queueTasks,
  set: (value: FaceQueueTask[]) => {
    faceSwap.value.queueTasks = value;
  },
});

const notice = computed({
  get: () => faceSwap.value.notice,
  set: (value) => {
    faceSwap.value.notice = value;
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

function createTask(): FaceTask {
  return {
    id: crypto.randomUUID(),
    collapsed: false,
    targetFiles: [],
    headFiles: [],
    accessoryFiles: [],
    manualText: "",
    ratioLabel: ratioOptions.value[0]?.label || appStore.publicConfig?.defaults.ratio || "",
  };
}

watch(
  () => appStore.publicConfig,
  (config) => {
    if (config && !tasks.value.length) {
      tasks.value = [createTask()];
    }
  },
  { immediate: true },
);

watch(
  ratioOptions,
  (options) => {
    tasks.value = tasks.value.map((task) => ({
      ...task,
      ratioLabel: options.some((item) => item.label === task.ratioLabel) ? task.ratioLabel : options[0]?.label || "",
    }));
  },
  { immediate: true },
);

function setNotice(type: "success" | "error", message: string) {
  notice.value = { type, message };
}

function addTask() {
  tasks.value.push(createTask());
}

function clearQueue() {
  queueTasks.value = [];
  appStore.addLog("批量换头任务列表已清空。");
}

function removeQueueTask(taskId: string) {
  queueTasks.value = queueTasks.value.filter((item) => item.id !== taskId);
}

function removeTask(taskId: string) {
  if (tasks.value.length === 1) {
    return;
  }
  const targetTask = tasks.value.find((task) => task.id === taskId);
  if (targetTask) {
    revokeUploadItems(targetTask.targetFiles);
    revokeUploadItems(targetTask.headFiles);
    revokeUploadItems(targetTask.accessoryFiles);
  }
  tasks.value = tasks.value.filter((task) => task.id !== taskId);
}

function toggleTask(task: FaceTask) {
  task.collapsed = !task.collapsed;
}

function openPreview(url: string, title: string) {
  previewImageUrl.value = url;
  previewImageTitle.value = title;
}

function closePreview() {
  previewImageUrl.value = "";
  previewImageTitle.value = "";
}

function firstResult(task: FaceQueueTask) {
  return task.results[0];
}

function startBatchFaceSwap() {
  if (submitting.value) {
    return;
  }

  submitting.value = true;
  notice.value = null;

  try {
    const submittedTasks: FaceQueueTask[] = tasks.value.map((task, index) => ({
      id: crypto.randomUUID(),
      title: `批量换头 ${index + 1}`,
      prompt: task.manualText.trim() || "批量换头任务",
      status: "running",
      results: [],
      targetFiles: task.targetFiles.map((item) => item.file),
      headFiles: task.headFiles.map((item) => item.file),
      accessoryFiles: task.accessoryFiles.map((item) => item.file),
      manualText: task.manualText,
      ratioLabel: task.ratioLabel,
    }));

    queueTasks.value = [...submittedTasks, ...queueTasks.value];
    appStore.addLog(`批量换头已提交 ${submittedTasks.length} 个任务。`);
    setNotice("success", `已提交 ${submittedTasks.length} 个批量换头任务，可继续提交新任务。`);

    for (const task of submittedTasks) {
      void runSubmittedTask(task);
    }
  } finally {
    submitting.value = false;
  }
}

async function runSubmittedTask(task: FaceQueueTask) {
  try {
    const response = await runFaceSwapApi(
      task.targetFiles,
      task.headFiles,
      task.accessoryFiles,
      task.manualText,
      appStore.buildCommonSettings(task.ratioLabel),
    );
    if (!response.ok) {
      throw new Error(response.message || `${task.title} 执行失败。`);
    }

    queueTasks.value = queueTasks.value.map((item) =>
      item.id === task.id
        ? {
            ...item,
            status: "success",
            results: response.data,
            prompt: response.data[0]?.prompt || item.prompt,
          }
        : item,
    );
    appStore.addSuccessCount(response.data.length);
    appStore.addLog(`${task.title} 已完成，生成 ${response.data.length} 张。`);
  } catch (error) {
    const message = getErrorMessage(error);
    queueTasks.value = queueTasks.value.map((item) =>
      item.id === task.id
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

function taskStatusText(status: FaceQueueTask["status"]) {
  if (status === "success") return "已完成";
  if (status === "error") return "失败";
  return "执行中";
}

function taskStatusEnglish(status: FaceQueueTask["status"]) {
  if (status === "success") return "Done";
  if (status === "error") return "Error";
  return "Running";
}
</script>

<template>
  <div class="desktop-module-grid">
    <section class="module-panel module-panel-left">
      <div class="module-title-bar">批量换头控制台</div>

      <div class="module-toolbar">
        <button class="mini-blue-button" type="button" @click="addTask()">+ 添加任务</button>
        <div class="toolbar-ready-text">就绪</div>
        <button class="mini-red-button" type="button" @click="clearQueue()">清空列表</button>
      </div>

      <div class="task-panel-scroll">
        <article v-for="(task, index) in tasks" :key="task.id" class="module-task-card">
          <div class="module-task-header">
            <div class="module-task-header-left">
              <button class="mini-indigo-button" type="button" @click="toggleTask(task)">
                {{ task.collapsed ? "展开" : "收起" }}
              </button>
              <div>
                <div class="module-task-title">换头任务 {{ index + 1 }}</div>
                <div class="module-task-meta">
                  模特图 {{ task.targetFiles.length }} 张 | 头部参考图 {{ task.headFiles.length }} 张 | 其他参考图
                  {{ task.accessoryFiles.length }} 张
                </div>
              </div>
            </div>
            <button class="mini-red-button" type="button" @click="removeTask(task.id)">删除</button>
          </div>

          <div v-if="!task.collapsed" class="task-card-body">
            <FileUploadField
              v-model="task.targetFiles"
              title="1. 批量模特图"
              button-text="批量上传模特图"
              empty-text="未上传模特图，可点击或拖拽图片到这里批量上传"
              accent-class="accent-purple"
            />

            <FileUploadField
              v-model="task.headFiles"
              title="2. 指定头部参考图"
              button-text="批量上传头部参考图"
              empty-text="未上传头部参考图，可点击或拖拽图片到这里批量上传"
              accent-class="accent-blue"
            />

            <FileUploadField
              v-model="task.accessoryFiles"
              title="3. 其他参考图"
              button-text="批量上传其他参考图"
              empty-text="未上传其他参考图，可点击或拖拽图片到这里批量上传"
              accent-class="accent-teal"
            />

            <label class="form-field">
              <span>4. 补充要求</span>
              <textarea
                v-model="task.manualText"
                class="desktop-textarea"
                placeholder="可补充首饰、鞋子、局部保留或其他约束"
              ></textarea>
            </label>

            <label class="form-field">
              <span>5. 输出比例</span>
              <select
                v-model="task.ratioLabel"
                class="desktop-select"
                :disabled="!appStore.currentModel?.supports_ratio_selection"
              >
                <option v-for="item in ratioOptions" :key="item.label" :value="item.label">
                  {{ item.label }}
                </option>
              </select>
            </label>
          </div>
        </article>
      </div>

      <button class="module-main-button green" type="button" :disabled="submitting" @click="startBatchFaceSwap()">
        {{ submitting ? "提交中..." : "开始批量换头" }}
      </button>

      <div v-if="notice" class="notice-banner" :class="notice.type === 'error' ? 'notice-error' : 'notice-success'">
        {{ notice.message }}
      </div>
    </section>

    <section class="queue-shell">
      <div class="queue-header">
        <span>换头任务队列</span>
        <span class="queue-count">{{ queueTasks.length }}</span>
      </div>

      <div v-if="!queueTasks.length" class="queue-empty">点击开始生成后，任务会自动出现在这里并开始执行</div>

      <div v-else class="result-list">
        <article v-for="(task, index) in queueTasks" :key="task.id" class="scene-task-card">
          <div class="task-thumb-frame">
            <button
              v-if="firstResult(task)"
              class="task-thumb-button"
              type="button"
              @click="openPreview(firstResult(task).url, firstResult(task).title || `任务 ${index + 1}`)"
            >
              <img :src="firstResult(task).url" :alt="firstResult(task).title" class="task-thumb-image" />
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
            <textarea v-model="task.prompt" class="desktop-textarea task task-prompt-box" placeholder="任务提示词..." />
            <div v-if="task.results.length > 1" class="module-task-meta">本任务生成 {{ task.results.length }} 张，缩略图显示第 1 张</div>
            <div v-if="task.error" class="task-error-text">{{ task.error }}</div>
          </div>

          <div class="task-action-column">
            <a
              v-if="firstResult(task)"
              class="mini-blue-button compact"
              :href="firstResult(task).url"
              target="_blank"
              rel="noreferrer"
            >
              查看
            </a>
            <button v-else class="mini-blue-button compact" type="button" disabled>查看</button>
            <div class="task-icon-actions">
              <a
                v-if="firstResult(task)"
                class="icon-action-button"
                :href="firstResult(task).url"
                :download="firstResult(task).file_name || firstResult(task).title"
                title="下载图片"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true" class="icon-action-svg">
                  <path d="M12 3v10m0 0 4-4m-4 4-4-4M5 17v2h14v-2" />
                </svg>
              </a>
              <button class="task-close-button compact" type="button" @click="removeQueueTask(task.id)">×</button>
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
