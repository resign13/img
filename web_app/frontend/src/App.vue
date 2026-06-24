<script setup lang="ts">
import { onMounted } from "vue";

import AppShell from "@/components/AppShell.vue";
import { useAppStore } from "@/stores/app";

const appStore = useAppStore();

onMounted(() => {
  void appStore.init();
});
</script>

<template>
  <AppShell>
    <RouterView v-slot="{ Component }">
      <KeepAlive>
        <component :is="Component" />
      </KeepAlive>
    </RouterView>
  </AppShell>
</template>
