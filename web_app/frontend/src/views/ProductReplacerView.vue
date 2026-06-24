<script setup lang="ts">
import { storeToRefs } from "pinia";
import { computed, watch } from "vue";

import { runReplacerApi } from "@/api/client";
import FileUploadField from "@/components/FileUploadField.vue";
import ResultQueue from "@/components/ResultQueue.vue";
import { useAppStore } from "@/stores/app";
import { useWorkspaceStore } from "@/stores/workspace";
import type { ReplacerTask } from "@/types";
import { getErrorMessage } from "@/utils/errors";
import { revokeUploadItems } from "@/utils/files";

const appStore = useAppStore();
const workspaceStore = useWorkspaceStore();
const { replacer } = storeToRefs(workspaceStore);

const tasks = computed({
  get: () => replacer.value.tasks,
  set: (value: ReplacerTask[]) => {
    replacer.value.tasks = value;
  },
});

const results = computed({
  get: () => replacer.value.results,
  set: (value) => {
    replacer.value.results = value;
  },
});

const loading = computed({
  get: () => replacer.value.loading,
  set: (value: boolean) => {
    replacer.value.loading = value;
  },
});

const notice = computed({
  get: () => replacer.value.notice,
  set: (value) => {
    replacer.value.notice = value;
  },
});

const ratioOptions = computed(() => {
  const all = appStore.publicConfig?.ratio_options ?? [];
  const currentModel = appStore.currentModel;
  if (!currentModel?.supports_ratio_selection || !currentModel.allowed_ratios.length) {
    return all;
  }
  return all.filter((item) => currentModel.allowed_ratios.includes(item.value));
});

function createTask(): ReplacerTask {
  return {
    id: crypto.randomUUID(),
    collapsed: false,
    sceneFiles: [],
    productFiles: [],
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

function clearResults() {
  results.value = [];
}

function removeTask(taskId: string) {
  if (tasks.value.length === 1) {
    return;
  }
  const targetTask = tasks.value.find((task) => task.id === taskId);
  if (targetTask) {
    revokeUploadItems(targetTask.sceneFiles);
    revokeUploadItems(targetTask.productFiles);
  }
  tasks.value = tasks.value.filter((task) => task.id !== taskId);
}

function toggleTask(task: ReplacerTask) {
  task.collapsed = !task.collapsed;
}

async function startBatchReplace() {
  loading.value = true;
  notice.value = null;
  results.value = [];

  try {
    const aggregated: ResultItem[] = [];
    for (const [index, task] of tasks.value.entries()) {
      const response = await runReplacerApi(
        task.sceneFiles.map((item) => item.file),
        task.productFiles.map((item) => item.file),
        task.manualText,
        appStore.buildCommonSettings(task.ratioLabel),
      );
      if (!response.ok) {
        throw new Error(response.message || `替换任务 ${index + 1} 执行失败。`);
      }
      aggregated.push(...response.data);
      appStore.addLog(`爆款替换任务 ${index + 1} 已完成，生成 ${response.data.length} 张。`);
    }
    results.value = aggregated;
    appStore.addSuccessCount(aggregated.length);
    setNotice("success", `爆款替换完成，共生成 ${aggregated.length} 张。`);
  } catch (error) {
    const message = getErrorMessage(error);
    appStore.addLog(message, "ERROR");
    setNotice("error", message);
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="desktop-module-grid">
    <section class="module-panel module-panel-left">
      <div class="module-title-bar">爆款替换控制台</div>

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
                <div class="module-task-title">替换任务 {{ index + 1 }}</div>
                <div class="module-task-meta">
                  模特图 {{ task.sceneFiles.length }} 张 | 产品参考图 {{ task.productFiles.length }} 张
                  <span v-if="task.manualText"> | 已填写补充要求</span>
                </div>
              </div>
            </div>
            <button class="mini-red-button" type="button" @click="removeTask(task.id)">删除</button>
          </div>

          <div v-if="!task.collapsed" class="task-card-body">
            <FileUploadField
              v-model="task.sceneFiles"
              title="1. 模特图 / 场景图"
              button-text="批量上传模特图"
              empty-text="未上传模特图"
              accent-class="accent-purple"
            />

            <FileUploadField
              v-model="task.productFiles"
              title="2. 产品参考图"
              button-text="批量上传产品参考图"
              empty-text="未上传产品参考图"
              accent-class="accent-blue"
            />

            <label class="form-field">
              <span>3. 补充要求</span>
              <textarea
                v-model="task.manualText"
                class="desktop-textarea"
                placeholder="可补充强调细节，比如面料、口袋、下摆、门襟等"
              ></textarea>
            </label>

            <label class="form-field">
              <span>4. 画面比例</span>
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

      <button class="module-main-button green" type="button" :disabled="loading" @click="startBatchReplace()">
        开始批量替换
      </button>

      <div v-if="notice" class="notice-banner" :class="notice.type === 'error' ? 'notice-error' : 'notice-success'">
        {{ notice.message }}
      </div>
    </section>

    <ResultQueue title="替换任务队列" :results="results" empty-text="暂无替换结果" />
  </div>
</template>
