<template>
  <div class="workspace-container">
    <!-- 顶部栏（对齐 FilesView「收录档案」风格） -->
    <div class="workspace-header">
      <div class="header-title">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6A8A9A" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
        </svg>
        <h2>我的数据空间</h2>
        <span v-if="chatStore.workspaces.length > 0" class="workspace-count">{{ chatStore.workspaces.length }}</span>
      </div>
      <button class="upload-btn" @click="pickDirectory" :disabled="picking">
        <span v-if="picking" class="loading-spinner"></span>
        <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          <line x1="12" y1="11" x2="12" y2="17"/>
          <line x1="9" y1="14" x2="15" y2="14"/>
        </svg>
        <span v-if="picking">选择中…</span>
        <span v-else>选择本地文件夹</span>
      </button>
    </div>

    <!-- 挂载表单（手动输入为目录选择器的 fallback，常驻显示） -->
    <div class="mount-section">
      <p v-if="pickHint" class="mount-hint">{{ pickHint }}</p>
      <div class="mount-form">
        <input
          v-model="mountPath"
          class="input path-input"
          type="text"
          placeholder="文件夹路径，如 /Users/teacher/期末数据"
          @keydown.enter="handleMount"
        />
        <input
          v-model="mountName"
          class="input name-input"
          type="text"
          placeholder="空间名称（可选）"
          @keydown.enter="handleMount"
        />
        <button class="btn btn-primary mount-submit" @click="handleMount" :disabled="!mountPath.trim() || mounting">
          {{ mounting ? '挂载中…' : '挂载' }}
        </button>
      </div>
      <p v-if="mountError" class="mount-error">{{ mountError }}</p>
    </div>

    <!-- 已挂载空间卡片列表 -->
    <div class="workspace-list">
      <div
        v-for="w in chatStore.workspaces"
        :key="w.id"
        class="workspace-card"
        :class="{ current: w.id === chatStore.currentWorkspaceId }"
      >
        <div class="card-main">
          <div class="card-title-row">
            <span class="card-name">{{ displayName(w.name) }}</span>
            <span class="card-type">{{ w.type === 'internal' ? '上传空间' : '本地挂载' }}</span>
            <span v-if="w.id === chatStore.currentWorkspaceId" class="current-badge">当前</span>
          </div>
          <div v-if="w.type === 'external' && w.source_path" class="card-path" :title="w.source_path">
            {{ w.source_path }}
          </div>
          <div class="card-output">
            <template v-if="editingOutputId === w.id">
              <input
                v-model="editingOutputValue"
                class="input output-edit-input"
                type="text"
                @keydown.enter="saveOutputPath(w)"
                @keydown.esc="cancelEditOutput"
              />
              <button class="btn btn-primary output-btn" @click="saveOutputPath(w)">保存</button>
              <button class="btn btn-ghost output-btn" @click="cancelEditOutput">取消</button>
            </template>
            <template v-else>
              <span class="output-label">输出到：<span class="output-value" :title="w.output_path">{{ w.output_path }}</span></span>
              <button class="btn btn-ghost output-btn edit-output-btn" @click="startEditOutput(w)">修改</button>
            </template>
          </div>
        </div>
        <div class="card-actions">
          <button
            v-if="w.id !== chatStore.currentWorkspaceId"
            class="btn btn-secondary switch-btn"
            @click="switchWorkspace(w)"
          >切换</button>
          <button
            v-if="w.type === 'external'"
            class="btn btn-ghost unmount-btn"
            @click="unmountWorkspace(w)"
          >卸载</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import { workspacesApi } from '@/api/workspaces'
import { systemApi } from '@/api/system'
import { stripTimestampPrefix } from '@/utils/display'

const router = useRouter()
const chatStore = useChatStore()

const mountPath = ref('')
const mountName = ref('')
const mounting = ref(false)
const mountError = ref('')
const picking = ref(false)
const pickHint = ref('')
const editingOutputId = ref(null)
const editingOutputValue = ref('')

function displayName(name) {
  return stripTimestampPrefix(name)
}

/**
 * 调起系统原生目录选择器，成功后回填路径输入框；
 * 用户取消 / 环境不支持（503）时提示并回退到手动输入。
 */
async function pickDirectory() {
  picking.value = true
  pickHint.value = ''
  try {
    const res = await systemApi.pickDirectory()
    if (res?.path) {
      mountPath.value = res.path
      // 默认空间名取文件夹名（去时间戳前缀）
      if (!mountName.value.trim()) {
        const base = String(res.path).replace(/\/+$/, '').split('/').pop()
        mountName.value = stripTimestampPrefix(base)
      }
    } else {
      pickHint.value = '未选择文件夹，可手动输入路径'
    }
  } catch (e) {
    pickHint.value = e.response?.status === 503
      ? '当前环境不支持系统目录选择器，请手动输入路径'
      : '打开目录选择器失败，请手动输入路径'
  } finally {
    picking.value = false
  }
}

async function handleMount() {
  const path = mountPath.value.trim()
  if (!path || mounting.value) return
  mountError.value = ''

  // 去重检查：已挂载过的路径不允许重复挂载
  const existing = chatStore.workspaces.find(
    w => w.type === 'external' && w.source_path === path
  )
  if (existing) {
    mountPath.value = ''
    mountName.value = ''
    await chatStore.setCurrentWorkspace(existing.id)
    router.push('/')
    return
  }

  mounting.value = true
  try {
    const res = await workspacesApi.mount({
      local_path: path,
      name: mountName.value.trim() || '本地文件夹'
    })
    mountPath.value = ''
    mountName.value = ''
    await chatStore.fetchWorkspaces()
    if (res.data?.id) {
      await chatStore.setCurrentWorkspace(res.data.id)
    }
    // 挂载发生在 /workspace 页：把"待显示弹窗"状态放 chat store，
    // 回到对话页后由 ChatView 消费并弹出 WelcomeRoadmapModal
    if (chatStore.roadmap?.questions?.length) {
      chatStore.pendingRoadmapModal = true
    }
    router.push('/')
  } catch (e) {
    mountError.value = '挂载失败：' + (e.response?.data?.detail || e.message)
  } finally {
    mounting.value = false
  }
}

async function switchWorkspace(w) {
  try {
    await chatStore.setCurrentWorkspace(w.id)
  } catch (e) {
    alert('切换数据空间失败：' + (e.response?.data?.detail || e.message))
  }
}

async function unmountWorkspace(w) {
  try {
    await workspacesApi.unmount(w.id)
    await chatStore.fetchWorkspaces()
  } catch (e) {
    alert('卸载失败：' + (e.response?.data?.detail || e.message))
  }
}

function startEditOutput(w) {
  editingOutputId.value = w.id
  editingOutputValue.value = w.output_path || ''
}

function cancelEditOutput() {
  editingOutputId.value = null
  editingOutputValue.value = ''
}

async function saveOutputPath(w) {
  const newPath = editingOutputValue.value.trim()
  try {
    if (newPath && newPath !== w.output_path) {
      await workspacesApi.updateOutputPath(w.id, newPath)
      await chatStore.fetchWorkspaces()
    }
  } catch (e) {
    alert('修改输出目录失败：' + (e.response?.data?.detail || e.message))
  } finally {
    cancelEditOutput()
  }
}

onMounted(() => {
  chatStore.fetchWorkspaces()
})
</script>

<style scoped>
.workspace-container {
  max-width: var(--content-width);
  margin: 0 auto;
  padding: var(--space-8) var(--space-6);
}

/* ── 顶部栏（对齐 FilesView） ── */
.workspace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-6);
  padding-bottom: var(--space-4);
  border-bottom: 0.5px solid #E0D8C0;
}

.header-title {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.header-title h2 {
  font-family: var(--font-serif);
  font-size: 17px;
  font-weight: 400;
  color: var(--ink-brown);
  letter-spacing: 0.5px;
  margin: 0;
}

.workspace-count {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--ink-brown-lighter);
  padding: 2px 8px;
  border: 0.5px solid #E0D8C0;
  min-width: 24px;
  text-align: center;
}

.upload-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  background: transparent;
  border: 0.5px solid #B0A080;
  color: var(--ink-brown);
  font-size: 12px;
  font-family: var(--font-serif);
  letter-spacing: 0.5px;
  cursor: pointer;
  transition: all var(--duration-fast) step-end;
}

.upload-btn:hover:not(:disabled) {
  background: var(--parchment-dark);
  border-color: var(--ink-brown-lighter);
}

.upload-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ── 挂载表单 ── */
.mount-section {
  margin-bottom: var(--space-8);
}

.mount-form {
  display: flex;
  gap: var(--space-3);
  align-items: center;
}

.path-input { flex: 3; }
.name-input { flex: 2; }

.mount-submit { flex-shrink: 0; }

.mount-hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.mount-error {
  margin-top: var(--space-2);
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--error-color);
  background: rgba(196, 85, 77, 0.04);
  padding: 3px 8px;
}

/* ── 空间卡片列表 ── */
.workspace-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.workspace-card {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: 14px 20px;
  background: var(--parchment-light);
  border: 0.5px solid rgba(79, 60, 43, 0.06);
  transition: all var(--duration-normal) step-end;
}

.workspace-card:hover {
  box-shadow:
    inset 0 0 24px rgba(11, 37, 61, 0.06),
    0 2px 8px rgba(79, 60, 43, 0.04);
  border-color: rgba(11, 37, 61, 0.15);
}

.workspace-card.current {
  border-color: #B0A080;
  background: #FAF6E8;
}

.card-main {
  flex: 1;
  min-width: 0;
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: 4px;
}

.card-name {
  font-family: var(--font-serif);
  font-size: 14px;
  color: var(--ink-brown);
  letter-spacing: 0.2px;
}

.card-type {
  font-size: 11px;
  color: var(--text-tertiary);
  border: 0.5px solid #E0D8C0;
  padding: 1px 6px;
}

.current-badge {
  font-size: 11px;
  color: var(--parchment-light);
  background: var(--slate-blue-darker);
  padding: 1px 6px;
}

.card-path {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.card-output {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 12px;
  color: var(--text-secondary);
}

.output-value {
  font-family: var(--font-mono);
  font-size: 11px;
}

.output-btn {
  padding: 2px 8px;
  font-size: 12px;
}

.output-edit-input {
  padding: 4px 8px;
  font-size: 12px;
  font-family: var(--font-mono);
  max-width: 380px;
}

.card-actions {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}

.card-actions .btn {
  padding: 4px 12px;
  font-size: 12px;
}

.unmount-btn:hover:not(:disabled) {
  color: var(--error-color);
}

/* ── 响应式 ── */
@media (max-width: 768px) {
  .workspace-container {
    padding: var(--space-5) var(--space-4);
  }

  .mount-form {
    flex-direction: column;
    align-items: stretch;
  }

  .workspace-card {
    flex-wrap: wrap;
  }

  .card-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
