<script setup lang="ts">
import { computed, ref, useId, watch } from "vue";
import type { ModelConfig, RatioOption } from "@/types";
import { normalizeRatio } from "@/utils/ratios";

const props = defineProps<{ modelValue: string; model: ModelConfig | null; options: RatioOption[]; label: string }>();
const emit = defineEmits<{ "update:modelValue": [value: string] }>();
const id = useId();
const field = ref<HTMLInputElement | HTMLSelectElement>();
const error = ref("");
const custom = computed(() => Boolean(props.model?.custom_ratio_max));
const description = computed(() => [custom.value ? `${id}-hint` : "", error.value ? `${id}-error` : ""].filter(Boolean).join(" ") || undefined);

function onInput(event: Event) {
  error.value = "";
  field.value?.setCustomValidity("");
  emit("update:modelValue", (event.target as HTMLInputElement).value);
}

function validate(report = true): boolean {
  const normalized = normalizeRatio(props.modelValue, props.model, props.options);
  error.value = normalized ? "" : custom.value
    ? `请输入正整数宽:高，范围为 1:${props.model!.custom_ratio_max} 至 ${props.model!.custom_ratio_max}:1。`
    : "请选择当前模型支持的画面比例。";
  field.value?.setCustomValidity(error.value);
  if (normalized) emit("update:modelValue", normalized);
  if (error.value && report) {
    field.value?.focus();
    field.value?.reportValidity();
  }
  return Boolean(normalized);
}

watch(() => props.model?.label, () => { error.value = ""; field.value?.setCustomValidity(""); });
defineExpose({ validate });
</script>

<template>
  <div class="form-field">
    <label :for="id">{{ label }}</label>
    <span v-if="custom" :id="`${id}-hint`" class="ratio-hint">可选预设，或输入宽:高（1:{{ model!.custom_ratio_max }} 至 {{ model!.custom_ratio_max }}:1）</span>
    <input v-if="custom" :id="id" ref="field" :value="modelValue" :list="`${id}-options`"
      class="desktop-select" name="ratio" type="text" required maxlength="11" autocomplete="off"
      autocapitalize="none" :spellcheck="false" :aria-describedby="description" :aria-invalid="Boolean(error)"
      @input="onInput" @blur="validate(false)" />
    <select v-else :id="id" ref="field" :value="modelValue" class="desktop-select" name="ratio" required
      :disabled="!model?.supports_ratio_selection" :aria-describedby="description" :aria-invalid="Boolean(error)" @change="onInput">
      <option v-for="option in options" :key="option.label" :value="option.label">{{ option.label }}</option>
    </select>
    <datalist v-if="custom" :id="`${id}-options`"><option v-for="option in options" :key="option.label" :value="option.value" /></datalist>
    <span v-if="error" :id="`${id}-error`" class="ratio-error">{{ error }}</span>
  </div>
</template>

<style scoped>
.ratio-hint { color: #ccc; font-size: 0.85rem; }
.ratio-error { color: #ffaaaa; font-size: 0.85rem; }
[aria-invalid="true"] { border-color: #ffaaaa; }
input:focus-visible, select:focus-visible { outline: 2px solid #75bfff; outline-offset: 2px; }
</style>
