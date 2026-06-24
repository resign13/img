import { defineStore } from "pinia";

import type {
  FaceTask,
  MultiReferenceTask,
  NoticeMessage,
  ReplacerTask,
  ResultItem,
  ScenePromptItem,
  UploadItem,
} from "@/types";

type SceneWorkspaceState = {
  productFiles: UploadItem[];
  promptItems: ScenePromptItem[];
  styleName: string;
  templateName: string;
  ratioLabel: string;
  extraInfo: string;
  loading: boolean;
  notice: NoticeMessage | null;
};

type MultiReferenceWorkspaceState = {
  referenceFiles: UploadItem[];
  prompt: string;
  ratioLabel: string;
  tasks: MultiReferenceTask[];
  loading: boolean;
  notice: NoticeMessage | null;
};

type ReplacerWorkspaceState = {
  tasks: ReplacerTask[];
  results: ResultItem[];
  loading: boolean;
  notice: NoticeMessage | null;
};

type FaceSwapWorkspaceState = {
  tasks: FaceTask[];
  results: ResultItem[];
  loading: boolean;
  notice: NoticeMessage | null;
};

export const useWorkspaceStore = defineStore("workspace", {
  state: () => ({
    scene: {
      productFiles: [],
      promptItems: [],
      styleName: "",
      templateName: "",
      ratioLabel: "",
      extraInfo: "",
      loading: false,
      notice: null,
    } as SceneWorkspaceState,
    multiReference: {
      referenceFiles: [],
      prompt: "",
      ratioLabel: "",
      tasks: [],
      loading: false,
      notice: null,
    } as MultiReferenceWorkspaceState,
    replacer: {
      tasks: [],
      results: [],
      loading: false,
      notice: null,
    } as ReplacerWorkspaceState,
    faceSwap: {
      tasks: [],
      results: [],
      loading: false,
      notice: null,
    } as FaceSwapWorkspaceState,
  }),
});
