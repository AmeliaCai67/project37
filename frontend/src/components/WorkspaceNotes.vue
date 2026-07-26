<template>
  <aside class="workspace-notes">
    <!-- 便利贴一：当前数据空间 -->
    <div class="note note-current">
      <div class="note-label">当前数据空间</div>
      <div class="note-value" :title="chatStore.currentWorkspace?.name">
        {{ currentName }}
      </div>
      <div v-if="chatStore.currentWorkspace" class="note-sub">
        {{ chatStore.currentWorkspace.type === 'internal' ? '上传空间' : '本地挂载' }}
      </div>
    </div>

    <!-- 便利贴二：切换空间 -->
    <div class="note note-switch">
      <button class="note-head" @click="switchOpen = !switchOpen">
        <span class="note-label">切换空间</span>
        <span class="note-arrow" :class="{ open: switchOpen }">▾</span>
      </button>
      <div v-if="switchOpen" class="switch-list">
        <button
          v-for="w in chatStore.workspaces"
          :key="w.id"
          class="switch-item"
          :class="{ active: w.id === chatStore.currentWorkspaceId }"
          @click="switchWorkspace(w)"
        >
          {{ displayName(w.name) }}
        </button>
      </div>
    </div>

    <!-- 便利贴三：输出路径 -->
    <div class="note note-output" @click="goWorkspace">
      <div class="note-label">输出路径</div>
      <div class="note-value output-value" :title="chatStore.currentWorkspace?.output_path">
        {{ chatStore.currentWorkspace?.output_path || '未设置' }}
      </div>
      <div class="note-sub">点击前往修改</div>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import { stripTimestampPrefix } from '@/utils/display'

const router = useRouter()
const chatStore = useChatStore()

const switchOpen = ref(false)

const currentName = computed(() => {
  const name = chatStore.currentWorkspace?.name
  return name ? stripTimestampPrefix(name) : '未选择'
})

function displayName(name) {
  return stripTimestampPrefix(name)
}

async function switchWorkspace(w) {
  try {
    await chatStore.setCurrentWorkspace(w.id)
    switchOpen.value = false
  } catch (e) {
    // 切换失败：提示并保持便利贴状态不变
    alert('切换数据空间失败：' + (e.response?.data?.detail || e.message))
  }
}

function goWorkspace() {
  router.push('/workspace')
}
</script>

<style scoped>
/* 常驻窄栏：复用 .index-card 语言（随机微旋转 + 双层柔和阴影） */
.workspace-notes {
  position: absolute;
  right: 2rem;
  top: var(--space-37);
  width: 200px;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  z-index: 10;
}

.note {
  background: #FCFAF5;
  border: 0.5px solid #E0D8C0;
  padding: 10px 14px;
  box-shadow:
    2px 3px 6px rgba(79, 60, 43, 0.06),
    3px 5px 12px rgba(79, 60, 43, 0.04);
  transition: all var(--duration-fast) step-end;
}

.note-current { transform: rotate(-0.7deg); }
.note-switch { transform: rotate(0.5deg); }
.note-output { transform: rotate(-0.4deg); cursor: pointer; }

.note:hover {
  box-shadow:
    3px 5px 10px rgba(79, 60, 43, 0.10),
    4px 8px 18px rgba(79, 60, 43, 0.06);
  transform: translateY(-1px) rotate(0deg);
}

.note-label {
  font-size: 11px;
  color: var(--text-tertiary);
  letter-spacing: 0.3px;
  margin-bottom: 4px;
}

.note-value {
  font-size: 13px;
  color: rgba(79, 60, 43, 0.75);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.note-sub {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 2px;
}

.output-value {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 400;
}

.note-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  font-family: var(--font-sans);
}

.note-head .note-label { margin-bottom: 0; }

.note-arrow {
  font-size: 10px;
  color: var(--text-tertiary);
  transition: transform var(--duration-fast) ease;
}

.note-arrow.open { transform: rotate(180deg); }

.switch-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 8px;
}

.switch-item {
  text-align: left;
  background: none;
  border: none;
  padding: 5px 8px;
  font-size: 12px;
  color: rgba(79, 60, 43, 0.50);
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: var(--font-sans);
}

.switch-item:hover {
  background: var(--parchment-dark);
  color: rgba(79, 60, 43, 0.75);
}

.switch-item.active {
  color: rgba(79, 60, 43, 0.75);
  font-weight: 500;
  background: var(--parchment-dark);
}

@media (max-width: 1100px) {
  .workspace-notes { display: none; }
}
</style>
