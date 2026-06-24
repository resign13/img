<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { runFaceSwapApi } from "@/api/client";
import FileUploadField from "@/components/FileUploadField.vue";
import ResultQueue from "@/components/ResultQueue.vue";
import { useAppStore } from "@/stores/app";
import type { ResultItem, UploadItem } from "@/types";
import { getErrorMessage } from "@/utils/errors";

type FaceTask = {
  id: string;
  collapsed: boolean;
  targetFiles: UploadItem[];
  headFiles: UploadItem[];
  accessoryFiles: UploadItem[];
  manualText: string;
  ratioLabel: string;
};

const appStore = useAppStore();
const tasks = ref<FaceTask[]>([]);
const results = ref<ResultItem[]>([]);
const loading = ref(false);
const notice = ref<{ type: "success" | "error"; message: string } | null>(null);

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

function addTask() {
  tasks.value.push(createTask());
}

function clearResults() {
  results.value = [];
}

function removeTask(taskId: string) {
  if (tasks.value.length === 1) {
    return;
  }
  tasks.value = tasks.value.filter((task) => task.id !== taskId);
}

function toggleTask(task: FaceTask) {
  task.collapsed = !task.collapsed;
}

async function startBatchFaceSwap() {
  loading.value = true;
  notice.value = null;
  results.value = [];

  try {
    const aggregated: ResultItem[] = [];
    for (const [index, task] of tasks.value.entries()) {
      const response = await runFaceSwapApi(
        task.targetFiles.map((item) => item.file),
        task.headFiles.map((item) => item.file),
        task.accessoryFiles.map((item) => item.file),
        task.manualText,
        appStore.buildCommonSettings(task.ratioLabel),
      );
      if (!response.ok) {
        throw new Error(response.message || `换头任务 ${index + 1} 执行失败。`);
      }
      aggregated.push(...response.data);
      appStore.addLog(`批量换头任务 ${index + 1} 已完成，生成 ${response.data.length} 张。`);
    }
    results.value = aggregated;
    appStore.addSuccessCount(aggregated.length);
    notice.value = { type: "success", message: `批量换头完成，共生成 ${aggregated.length} 张。` };
  } catch (error) {
    const message = getErrorMessage(error);
    appStore.addLog(message, "ERROR");
    notice.value = { type: "error", message };
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="desktop-module-grid">
    <section class="module-panel module-panel-left">
      <div class="module-title-bar">批量换头控制台</div>

      <div class="module-toolbar">
        <button class="mini-blue-button" type="button" @click="addTask()">+ 添加任务</button>
        <div class="toolbar-ready-text">就绪</div>
        <button class="mini-red-button" type="button" @click="clearResults()">清空结果</button>
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
              empty-text="未上传模特图"
              accent-class="accent-purple"
            />

            <FileUploadField
              v-model="task.headFiles"
              title="2. 指定头部参考图"
              button-text="批量上传头部参考图"
              empty-text="未上传头部参考图"
              accent-class="accent-blue"
            />

            <FileUploadField
              v-model="task.accessoryFiles"
              title="3. 其他参考图"
              button-text="批量上传其他参考图"
              empty-text="未上传其他参考图"
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

      <button class="module-main-button green" type="button" :disabled="loading" @click="startBatchFaceSwap()">
        开始批量换头
      </button>

      <div v-if="notice" class="notice-banner" :class="notice.type === 'error' ? 'notice-error' : 'notice-success'">
        {{ notice.message }}
      </div>
    </section>

    <ResultQueue title="换头任务队列" :results="results" empty-text="暂无换头结果" />
  </div>
</template>
