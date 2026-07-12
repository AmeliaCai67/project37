<template>
  <div class="workspace-bar">
    <div class="workspace-info">
      <span class="workspace-name">{{ currentWorkspace?.name || '未选择工作区' }}</span>
      <span v-if="typeLabel" class="workspace-type">{{ typeLabel }}</span>
    </div>

    <select v-model="selectedId" class="workspace-select">
      <option v-for="w in workspaces" :key="w.id" :value="w.id">
        {{ w.name }}{{ w.type === 'external' && w.source_path ? ' (' + w.source_path + ')' : '' }}
      </option>
    </select>

    <button class="btn btn-secondary mount-btn" @click="emit('mount')">
      挂载文件夹
    </button>

    <div v-if="currentWorkspace" class="output-path">
      <span>输出到：{{ currentWorkspace.output_path }}</span>
      <button class="btn btn-ghost edit-output-btn" @click="editOutputPath">修改</button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useChatStore } from '@/stores/chat'
import { workspacesApi } from '@/api/workspaces'

const store = useChatStore()
const emit = defineEmits(['mount'])

const currentWorkspace = computed(() => store.currentWorkspace)
const workspaces = computed(() => store.workspaces)

const selectedId = computed({
  get: () => store.currentWorkspaceId,
  set: (val) => store.setCurrentWorkspace(Number(val))
})

const typeLabel = computed(() => {
  if (!currentWorkspace.value) return ''
  return currentWorkspace.value.type === 'internal' ? '上传空间' : '本地挂载'
})

async function editOutputPath() {
  const current = currentWorkspace.value
  if (!current) return

  const newPath = window.prompt('修改输出目录：', current.output_path)
  if (!newPath || newPath === current.output_path) return

  try {
    await workspacesApi.updateOutputPath(current.id, newPath)
    await store.fetchWorkspaces()
  } catch (error) {
    console.error('修改输出目录失败:', error)
  }
}
</script>

<style scoped>
.workspace-bar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-4);
  border-bottom: 1px solid var(--border-light);
  font-size: 14px;
  background: var(--surface-color);
}

.workspace-info {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.workspace-name {
  font-weight: 600;
  color: var(--text-primary);
}

.workspace-type {
  color: var(--text-secondary);
  font-size: 12px;
}

.workspace-select {
  padding: 4px 8px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--surface-color);
  color: var(--text-primary);
  font-size: 13px;
}

.output-path {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-left: auto;
  color: var(--text-secondary);
  font-size: 13px;
}

.output-path .btn {
  padding: 2px 8px;
  font-size: 12px;
}
</style>
