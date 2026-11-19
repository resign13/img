import type { ModelConfig, RatioOption } from "@/types";

export function normalizeRatio(value: string, model: ModelConfig | null, options: RatioOption[] = []): string | null {
  const ratio = value.trim().replace(/：/g, ":");
  const preset = options.find((option) => option.label === ratio || option.value === ratio);
  const actual = preset?.value ?? ratio;
  if (model?.allowed_ratios.includes(actual)) return actual;
  const maximum = model?.custom_ratio_max;
  const match = maximum ? /^([0-9]{1,5})\s*:\s*([0-9]{1,5})$/.exec(actual) : null;
  if (!match || !maximum) return null;
  const width = Number(match[1]);
  const height = Number(match[2]);
  return width > 0 && height > 0 && Math.max(width, height) <= maximum * Math.min(width, height)
    ? `${width}:${height}` : null;
}
