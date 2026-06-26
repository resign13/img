export type ModelConfig = {
  label: string;
  supports_ratio_selection: boolean;
  supports_resolution_selection: boolean;
  supports_text_only_generation: boolean;
  allowed_ratios: string[];
  allowed_resolutions: string[];
};

export type RatioOption = {
  label: string;
  value: string;
};

export type PublicConfigResponse = {
  models: ModelConfig[];
  ratio_options: RatioOption[];
  key_status: {
    llm_key_configured: boolean;
    img_key_configured: boolean;
    img_key_line2_configured: boolean;
  };
  defaults: {
    image_model: string;
    image_resolution: string;
    ratio: string;
    compress_enable: boolean;
    compress_target: number;
    style: string;
    template: string;
    extra_info: string;
    output_path: string;
  };
  styles: Record<string, string>;
  templates: Record<string, string>;
};

export type UploadItem = {
  id: string;
  file: File;
  name: string;
  previewUrl: string;
};

export type ResultItem = {
  title: string;
  prompt: string;
  url: string;
  source_name?: string;
  file_name?: string;
};

export type HistoryImageItem = {
  id: string;
  url: string;
  thumbnail_url: string;
  file_name: string;
  title: string;
  prompt: string;
  source_name: string;
  module: string;
  module_label: string;
  session_id: string;
  session_label: string;
  created_at: number;
  created_at_text: string;
  size_bytes: number;
};

export type HistoryImagePage = {
  items: HistoryImageItem[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
};

export type ScenePromptItem = {
  id: string;
  text: string;
  status: "waiting" | "running" | "success" | "error";
  result?: ResultItem;
  error?: string;
  sourceFile?: File;
  ratioLabel?: string;
};

export type GeneratedTaskStatus = "running" | "success" | "error";

export type NoticeMessage = {
  type: "success" | "error";
  message: string;
};

export type ReplacerTask = {
  id: string;
  collapsed: boolean;
  sceneFiles: UploadItem[];
  productFiles: UploadItem[];
  manualText: string;
  ratioLabel: string;
};

export type ReplacerQueueTask = {
  id: string;
  title: string;
  prompt: string;
  status: GeneratedTaskStatus;
  results: ResultItem[];
  error?: string;
  sceneFiles: File[];
  productFiles: File[];
  manualText: string;
  ratioLabel: string;
};

export type FaceTask = {
  id: string;
  collapsed: boolean;
  targetFiles: UploadItem[];
  headFiles: UploadItem[];
  accessoryFiles: UploadItem[];
  manualText: string;
  ratioLabel: string;
};

export type FaceQueueTask = {
  id: string;
  title: string;
  prompt: string;
  status: GeneratedTaskStatus;
  results: ResultItem[];
  error?: string;
  targetFiles: File[];
  headFiles: File[];
  accessoryFiles: File[];
  manualText: string;
  ratioLabel: string;
};

export type MultiReferenceTask = {
  id: string;
  prompt: string;
  status: "running" | "success" | "error";
  result?: ResultItem;
  error?: string;
  referenceFiles: File[];
  ratioLabel: string;
};
