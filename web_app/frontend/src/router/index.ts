import { createRouter, createWebHistory } from "vue-router";

import FaceSwapView from "@/views/FaceSwapView.vue";
import MultiReferenceView from "@/views/MultiReferenceView.vue";
import ProductReplacerView from "@/views/ProductReplacerView.vue";
import SceneGeneratorView from "@/views/SceneGeneratorView.vue";
import TaskHistoryView from "@/views/TaskHistoryView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/scene" },
    { path: "/scene", name: "scene", component: SceneGeneratorView },
    { path: "/replacer", name: "replacer", component: ProductReplacerView },
    { path: "/multi-reference", name: "multi-reference", component: MultiReferenceView },
    { path: "/face-swap", name: "face-swap", component: FaceSwapView },
    { path: "/history", name: "history", component: TaskHistoryView },
  ],
});

export default router;
