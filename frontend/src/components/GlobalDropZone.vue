<template>
  <!-- 拖拽遮罩 — 仅在文件从外部拖入时显示 -->
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="isDragging"
        class="drop-overlay"
        @dragover.prevent="handleOverlayDragOver"
        @drop.prevent="handleDrop"
        @dragleave.prevent="handleOverlayDragLeave"
      >
        <div class="drop-zone">
          <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          <p class="drop-hint">释放文件以上传</p>
          <p class="drop-sub">支持 CSV、Excel、PDF、TXT 等格式</p>
        </div>
      </div>
    </Transition>
  </Teleport>

  <!-- 上传进度 / 结果提示 -->
  <Teleport to="body">
    <div class="upload-toasts">
      <TransitionGroup name="toast">
        <div
          v-for="task in uploadTasks"
          :key="task.id"
          class="upload-toast"
          :class="task.status"
        >
          <div class="toast-row">
            <span class="toast-icon">
              <svg v-if="task.status === 'uploading'" class="spin-icon" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
              </svg>
              <svg v-else-if="task.status === 'success'" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <line x1="15" y1="9" x2="9" y2="15"/>
                <line x1="9" y1="9" x2="15" y2="15"/>
              </svg>
            </span>
            <div class="toast-body">
              <span class="toast-filename" :title="task.filename">{{ task.filename }}</span>
              <span class="toast-message">{{ task.message }}</span>
            </div>
            <button v-if="task.status !== 'uploading'" class="toast-close" @click="removeTask(task.id)" aria-label="关闭">
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
          <div v-if="task.status === 'uploading'" class="toast-progress">
            <div class="toast-progress-bar" :style="{ width: task.progress + '%' }"></div>
          </div>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useUserStore } from '@/stores/user'
import { filesApi } from '@/api/files'

const userStore = useUserStore()

const isDragging = ref(false)
const uploadTasks = ref([])
let dragCounter = 0

// ── 拖拽事件处理 ──
function handleWindowDragEnter(e) {
  e.preventDefault()
  if (!userStore.canUpload) return
  if (e.dataTransfer.types && Array.from(e.dataTransfer.types).includes('Files')) {
    dragCounter++
    isDragging.value = true
  }
}

function handleWindowDragOver(e) {
  e.preventDefault()
}

function handleWindowDragLeave(e) {
  e.preventDefault()
  if (!userStore.canUpload) return
  dragCounter--
  if (dragCounter <= 0) {
    isDragging.value = false
    dragCounter = 0
  }
}

function handleOverlayDragOver(e) {
  e.preventDefault()
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy'
}

function handleOverlayDragLeave(e) {
  e.preventDefault()
}

function handleDrop(e) {
  e.preventDefault()
  isDragging.value = false
  dragCounter = 0

  const files = e.dataTransfer?.files
  if (!files || files.length === 0) return

  uploadFiles(Array.from(files))
}

// ── 上传逻辑 ──
function uploadFiles(files) {
  for (const file of files) {
    const task = {
      id: Date.now() + Math.random(),
      filename: file.name,
      progress: 0,
      status: 'uploading',
      message: '上传中...'
    }
    uploadTasks.value.unshift(task)

    filesApi
      .upload(file, (percent) => {
        task.progress = percent
      })
      .then(() => {
        task.status = 'success'
        task.message = '上传成功，已收录'
        task.progress = 100
        // 通知各视图刷新文件列表
        window.dispatchEvent(new CustomEvent('files-updated'))
        // 3 秒后自动移除成功提示
        setTimeout(() => removeTask(task.id), 3000)
      })
      .catch((error) => {
        task.status = 'error'
        task.message = error.response?.data?.detail || error.message || '上传失败'
        task.progress = 0
      })
  }
}

function removeTask(id) {
  const idx = uploadTasks.value.findIndex((t) => t.id === id)
  if (idx > -1) uploadTasks.value.splice(idx, 1)
}

onMounted(() => {
  window.addEventListener('dragenter', handleWindowDragEnter)
  window.addEventListener('dragover', handleWindowDragOver)
  window.addEventListener('dragleave', handleWindowDragLeave)
  window.addEventListener('drop', handleWindowDragLeave)
})

onUnmounted(() => {
  window.removeEventListener('dragenter', handleWindowDragEnter)
  window.removeEventListener('dragover', handleWindowDragOver)
  window.removeEventListener('dragleave', handleWindowDragLeave)
  window.removeEventListener('drop', handleWindowDragLeave)
})
</script>

<style scoped>
/* ── 拖拽遮罩 ── */
.drop-overlay {
  position: fixed;
  inset: 56px 0 0 0; /* 顶部留出导航栏 */
  z-index: 90;
  background: rgba(251, 248, 235, 0.85);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: all;
}

.drop-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-4);
  padding: 48px 64px;
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-lg);
  background: var(--parchment-light);
  color: var(--ink-brown-light);
  transition: all var(--duration-fast) ease;
}

.drop-zone svg {
  color: var(--slate-blue-dark);
}

.drop-hint {
  font-size: 16px;
  font-weight: 500;
  color: var(--ink-brown);
  margin: 0;
}

.drop-sub {
  font-size: 12px;
  color: var(--text-tertiary);
  margin: 0;
}

/* ── 过渡动画 ── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--duration-normal) var(--ease-out);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* ── Toast 容器 ── */
.upload-toasts {
  position: fixed;
  top: 68px;
  right: 16px;
  z-index: 110;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 320px;
  pointer-events: none;
}

.upload-toast {
  pointer-events: all;
  background: var(--parchment-light);
  border: 0.5px solid var(--border-color);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  box-shadow: var(--shadow-lg);
  font-size: 13px;
  transition: all var(--duration-normal) var(--ease-out);
}

.upload-toast.success {
  border-left: 3px solid var(--success-color);
}

.upload-toast.error {
  border-left: 3px solid var(--error-color);
}

.upload-toast.uploading {
  border-left: 3px solid var(--slate-blue-dark);
}

.toast-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toast-icon {
  flex-shrink: 0;
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
}

.upload-toast.success .toast-icon {
  color: var(--success-color);
}

.upload-toast.error .toast-icon {
  color: var(--error-color);
}

.upload-toast.uploading .toast-icon {
  color: var(--slate-blue-dark);
}

.spin-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.toast-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.toast-filename {
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.toast-message {
  font-size: 11px;
  color: var(--text-tertiary);
}

.toast-close {
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: 2px;
  display: flex;
  align-items: center;
  border-radius: var(--radius-sm);
  transition: all var(--duration-fast) ease;
}

.toast-close:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

/* 进度条 */
.toast-progress {
  margin-top: 8px;
  height: 3px;
  background: var(--border-light);
  border-radius: 2px;
  overflow: hidden;
}

.toast-progress-bar {
  height: 100%;
  background: var(--slate-blue-dark);
  border-radius: 2px;
  transition: width 0.2s linear;
}

/* Toast 进入/离开动画 */
.toast-enter-active,
.toast-leave-active {
  transition: all var(--duration-normal) var(--ease-out);
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>
