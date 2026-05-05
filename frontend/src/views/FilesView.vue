<template>
  <div class="files-container">
    <!-- 顶部栏 -->
    <div class="files-header">
      <div class="header-title">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6A8A9A" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="7" height="7" rx="0.5"/>
          <rect x="14" y="3" width="7" height="7" rx="0.5"/>
          <rect x="3" y="14" width="7" height="7" rx="0.5"/>
          <rect x="14" y="14" width="7" height="7" rx="0.5"/>
        </svg>
        <h2>科学索引 · 文件档案</h2>
        <span v-if="files.length > 0" class="file-count">{{ files.length }}</span>
      </div>
      <button
        v-if="userStore.canUpload"
        class="upload-btn"
        @click="triggerUpload"
        :disabled="uploading"
      >
        <span v-if="uploading" class="loading-spinner"></span>
        <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
          <line x1="12" y1="5" x2="12" y2="19"/>
          <line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        <span v-if="uploading">上传中 {{ uploadProgress }}%</span>
        <span v-else>收录档案</span>
      </button>
      <input
        ref="fileInput"
        type="file"
        multiple
        accept=".pdf,.docx,.csv,.xlsx,.txt,.json,.md"
        style="display: none"
        @change="handleFileChange"
      />
    </div>

    <!-- 空状态 -->
    <div v-if="files.length === 0" class="empty-cabinet">
      <div class="empty-geometry">
        <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64" fill="none">
          <rect x="4" y="4" width="56" height="56" stroke="#B0A080" stroke-width="0.5"/>
          <rect x="12" y="12" width="40" height="40" stroke="#B0A080" stroke-width="0.5"/>
          <line x1="32" y1="12" x2="32" y2="52" stroke="#B0A080" stroke-width="0.5"/>
          <line x1="12" y1="32" x2="52" y2="32" stroke="#B0A080" stroke-width="0.5"/>
        </svg>
      </div>
      <p class="empty-title">档案柜为空</p>
      <p v-if="userStore.canUpload" class="empty-tip">
        点击「收录档案」将数据文件纳入索引
      </p>
      <p v-else class="empty-tip">
        请联系管理员收录文件
      </p>
    </div>

    <!-- 文件索引卡片列表 -->
    <TransitionGroup v-else name="file-list" tag="div" class="files-cabinet">
      <div
        v-for="file in files"
        :key="file.id"
        class="file-index-card"
        :class="{ processing: file.status === 'processing' }"
      >
        <!-- 精密几何图标 -->
        <div class="file-geometry">
          <!-- XLSX — 矩阵网格 + 黄铜卡尺刻度 -->
          <svg v-if="getFileType(file.filename) === 'xlsx'" width="46" height="46" viewBox="0 0 46 46" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="10" y="8" width="11" height="11" stroke="#0B253D" stroke-width="0.8"/>
            <rect x="25" y="8" width="11" height="11" stroke="#0B253D" stroke-width="0.8"/>
            <rect x="10" y="23" width="11" height="11" stroke="#0B253D" stroke-width="0.8"/>
            <rect x="25" y="23" width="11" height="11" stroke="#0B253D" stroke-width="0.8"/>
            <line x1="15.5" y1="8" x2="15.5" y2="34" stroke="#0B253D" stroke-width="0.3"/>
            <line x1="10" y1="13.5" x2="36" y2="13.5" stroke="#0B253D" stroke-width="0.3"/>
            <text x="23" y="43" text-anchor="middle" fill="#0B253D" font-family="'Courier New', monospace" font-size="5.5" font-weight="700" letter-spacing="1.2">XLSX</text>
          </svg>
          <!-- PDF — 黄金分割比例尺 -->
          <svg v-else-if="getFileType(file.filename) === 'pdf'" width="46" height="46" viewBox="0 0 46 46" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="8" y="6" width="30" height="28" stroke="#0B253D" stroke-width="0.8"/>
            <line x1="20" y1="6" x2="20" y2="34" stroke="#0B253D" stroke-width="0.8"/>
            <line x1="8" y1="16" x2="38" y2="16" stroke="#0B253D" stroke-width="0.4" stroke-dasharray="1.5 2"/>
            <line x1="8" y1="24" x2="38" y2="24" stroke="#0B253D" stroke-width="0.8"/>
            <circle cx="20" cy="20" r="1.2" fill="#0B253D"/>
            <text x="23" y="43" text-anchor="middle" fill="#0B253D" font-family="'Courier New', monospace" font-size="5.5" font-weight="700" letter-spacing="1.2">PDF</text>
          </svg>
          <!-- CSV — 散点序列 -->
          <svg v-else-if="getFileType(file.filename) === 'csv'" width="46" height="46" viewBox="0 0 46 46" fill="none" xmlns="http://www.w3.org/2000/svg">
              <line x1="6" y1="18" x2="40" y2="18" stroke="#0B253D" stroke-width="0.5"/>
            <line x1="6" y1="28" x2="40" y2="28" stroke="#0B253D" stroke-width="0.5"/>
            <circle cx="11" cy="10" r="1.8" stroke="#0B253D" stroke-width="0.7"/>
            <circle cx="20" cy="7" r="1.8" stroke="#0B253D" stroke-width="0.7"/>
            <circle cx="30" cy="11" r="1.8" stroke="#0B253D" stroke-width="0.7"/>
            <circle cx="35" cy="22" r="1.8" stroke="#0B253D" stroke-width="0.7"/>
            <circle cx="16" cy="22" r="1.8" stroke="#0B253D" stroke-width="0.7"/>
            <circle cx="25" cy="32" r="1.8" stroke="#0B253D" stroke-width="0.7"/>
            <circle cx="8" cy="32" r="1.8" stroke="#0B253D" stroke-width="0.7"/>
            <text x="23" y="43" text-anchor="middle" fill="#0B253D" font-family="'Courier New', monospace" font-size="5.5" font-weight="700" letter-spacing="1.2">CSV</text>
          </svg>
          <!-- DOCX — 文档线框 -->
          <svg v-else-if="getFileType(file.filename) === 'docx'" width="46" height="46" viewBox="0 0 46 46" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="10" y="5" width="26" height="32" stroke="#0B253D" stroke-width="0.8"/>
            <line x1="15" y1="11" x2="31" y2="11" stroke="#0B253D" stroke-width="0.7"/>
            <line x1="15" y1="16" x2="28" y2="16" stroke="#0B253D" stroke-width="0.5"/>
            <line x1="15" y1="20" x2="25" y2="20" stroke="#0B253D" stroke-width="0.5"/>
            <line x1="15" y1="24" x2="20" y2="24" stroke="#0B253D" stroke-width="0.4"/>
            <text x="23" y="43" text-anchor="middle" fill="#0B253D" font-family="'Courier New', monospace" font-size="5.5" font-weight="700" letter-spacing="1.2">DOCX</text>
          </svg>
          <!-- TXT — 等宽文本行 -->
          <svg v-else-if="getFileType(file.filename) === 'txt'" width="46" height="46" viewBox="0 0 46 46" fill="none" xmlns="http://www.w3.org/2000/svg">
              <line x1="9" y1="10" x2="37" y2="10" stroke="#0B253D" stroke-width="0.8"/>
            <line x1="9" y1="15" x2="33" y2="15" stroke="#0B253D" stroke-width="0.6"/>
            <line x1="9" y1="20" x2="35" y2="20" stroke="#0B253D" stroke-width="0.8"/>
            <line x1="9" y1="25" x2="28" y2="25" stroke="#0B253D" stroke-width="0.5"/>
            <line x1="9" y1="30" x2="37" y2="30" stroke="#0B253D" stroke-width="0.8"/>
            <text x="23" y="43" text-anchor="middle" fill="#0B253D" font-family="'Courier New', monospace" font-size="5.5" font-weight="700" letter-spacing="1.2">TXT</text>
          </svg>
          <!-- JSON — 结构化花括号 -->
          <svg v-else-if="getFileType(file.filename) === 'json'" width="46" height="46" viewBox="0 0 46 46" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M17 8 h-2 Q12 8, 12 11 v5 Q12 19, 15 19 h2" stroke="#0B253D" stroke-width="0.8"/>
            <path d="M29 8 h2 q3 0, 3 3 v5 q0 3, -3 3 h-2" stroke="#0B253D" stroke-width="0.8"/>
            <line x1="19" y1="8" x2="19" y2="34" stroke="#0B253D" stroke-width="0.4" opacity="0.5"/>
            <line x1="27" y1="8" x2="27" y2="34" stroke="#0B253D" stroke-width="0.4" opacity="0.5"/>
            <rect x="19" y="27" width="8" height="7" stroke="#0B253D" stroke-width="0.5" opacity="0.4"/>
            <text x="23" y="43" text-anchor="middle" fill="#0B253D" font-family="'Courier New', monospace" font-size="5.5" font-weight="700" letter-spacing="1.2">JSON</text>
          </svg>
          <!-- MD — 标记语言井号 -->
          <svg v-else-if="getFileType(file.filename) === 'md'" width="46" height="46" viewBox="0 0 46 46" fill="none" xmlns="http://www.w3.org/2000/svg">
              <line x1="12" y1="7" x2="12" y2="35" stroke="#0B253D" stroke-width="0.8"/>
            <line x1="18" y1="7" x2="18" y2="35" stroke="#0B253D" stroke-width="0.8"/>
            <line x1="10" y1="14" x2="20" y2="14" stroke="#0B253D" stroke-width="0.8"/>
            <line x1="10" y1="22" x2="20" y2="22" stroke="#0B253D" stroke-width="0.8"/>
            <line x1="25" y1="11" x2="37" y2="11" stroke="#0B253D" stroke-width="0.5"/>
            <line x1="25" y1="18" x2="33" y2="18" stroke="#0B253D" stroke-width="0.4"/>
            <text x="23" y="43" text-anchor="middle" fill="#0B253D" font-family="'Courier New', monospace" font-size="5.5" font-weight="700" letter-spacing="1.2">MD</text>
          </svg>
          <!-- default — 通用档案折角 -->
          <svg v-else width="46" height="46" viewBox="0 0 46 46" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="9" y="6" width="28" height="32" stroke="#0B253D" stroke-width="0.8"/>
            <path d="M9 6 L18 6 L9 15 Z" fill="#0B253D" opacity="0.08" stroke="#0B253D" stroke-width="0.5"/>
            <line x1="15" y1="20" x2="31" y2="20" stroke="#0B253D" stroke-width="0.5"/>
            <line x1="15" y1="25" x2="28" y2="25" stroke="#0B253D" stroke-width="0.4"/>
          </svg>
        </div>

        <!-- 文件信息 -->
        <div class="file-info">
          <div class="file-name" :title="file.original_name || file.filename">
            {{ file.original_name || file.filename }}
          </div>
          <div class="file-meta">
            <span class="meta-item size">{{ formatSize(file.size) }}</span>
            <span class="meta-divider">·</span>
            <span class="meta-item date">{{ formatDate(file.uploaded_at) }}</span>
            <span class="meta-divider">·</span>
            <span class="meta-item status" :class="file.status">
              <span v-if="file.status === 'processing'" class="pulse-indicator"></span>
              {{ getStatusText(file.status) }}
            </span>
          </div>
          <div v-if="file.status === 'error' && file.error_message" class="file-error">
            {{ file.error_message }}
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="file-actions">
          <button class="action-btn" title="检视档案" @click="previewFile(file)">
            <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="3"/>
              <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/>
            </svg>
          </button>
          <button
            v-if="userStore.canDelete"
            class="action-btn"
            title="移出档案柜"
            @click="deleteFile(file)"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
              <line x1="5" y1="5" x2="19" y2="19"/>
              <line x1="19" y1="5" x2="5" y2="19"/>
            </svg>
          </button>
        </div>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useUserStore } from '@/stores/user'
import { filesApi } from '@/api/files'

const userStore = useUserStore()

const files = ref([])
const fileInput = ref(null)
const uploading = ref(false)
const uploadProgress = ref(0)

function triggerUpload() {
  fileInput.value?.click()
}

async function handleFileChange(event) {
  const selectedFiles = event.target.files
  if (!selectedFiles.length) return

  uploading.value = true
  uploadProgress.value = 0

  for (const file of selectedFiles) {
    try {
      await filesApi.upload(file, (progress) => {
        uploadProgress.value = progress
      })
    } catch (error) {
      alert(`上传 ${file.name} 失败: ${error.message}`)
    }
  }

  uploading.value = false
  uploadProgress.value = 0
  event.target.value = ''
  loadFiles()
}

async function loadFiles() {
  try {
    const res = await filesApi.getList()
    files.value = res.data || []
  } catch (error) {
    console.error('加载文件失败:', error)
  }
}

async function deleteFile(file) {
  if (!confirm(`确定要将 ${file.original_name || file.name} 移出档案柜吗？`)) {
    return
  }

  try {
    await filesApi.delete(file.id)
    loadFiles()
  } catch (error) {
    alert('删除失败: ' + error.message)
  }
}

function previewFile(file) {
  alert('检视功能开发中')
}

function getFileType(filename) {
  const ext = filename.split('.').pop().toLowerCase()
  const types = { pdf: 'pdf', docx: 'docx', csv: 'csv', xlsx: 'xlsx', txt: 'txt', json: 'json', md: 'md' }
  return types[ext] || 'default'
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN')
}

function getStatusText(status) {
  const texts = {
    pending: '待索引',
    processing: '提取中',
    ready: '已收录',
    error: '收录失败'
  }
  return texts[status] || status
}

onMounted(() => {
  loadFiles()
})
</script>

<style scoped>
/* ══════════════════════════════════════
   科学索引 · 文件档案柜
   ══════════════════════════════════════ */
.files-container {
  max-width: var(--content-width);
  margin: 0 auto;
  padding: var(--space-8) var(--space-6);
}

/* ── 顶部栏 ── */
.files-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-8);
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

.file-count {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--ink-brown-lighter);
  padding: 2px 8px;
  border: 0.5px solid #E0D8C0;
  border-radius: 0;
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
  border-radius: 0;
  color: var(--ink-brown);
  font-size: 12px;
  font-family: var(--font-serif);
  font-weight: 400;
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

/* ── 空档案柜 ── */
.empty-cabinet {
  text-align: center;
  padding: 80px 40px;
}

.empty-geometry {
  display: flex;
  justify-content: center;
  margin-bottom: var(--space-6);
  opacity: 0.5;
}

.empty-title {
  font-family: var(--font-serif);
  font-size: 16px;
  color: var(--ink-brown);
  margin-bottom: var(--space-2);
  letter-spacing: 0.3px;
}

.empty-tip {
  font-size: 13px;
  color: var(--text-tertiary);
}

/* ── 文件柜列表 ── */
.files-cabinet {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* ── 索引卡片行 ── */
.file-index-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-5);
  padding: 14px 20px;
  background: var(--parchment-light);
  border: 0.5px solid rgba(79, 60, 43, 0.06);
  border-radius: 0;
  transition: all var(--duration-normal) step-end;
}

/* 折角 — 模拟纸质档案的物理形态 */
.file-index-card::after {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  width: 16px;
  height: 16px;
  background: linear-gradient(135deg, transparent 50%, var(--parchment) 50%);
  border-bottom: 0.5px solid rgba(79, 60, 43, 0.04);
  z-index: 1;
}

/* 悬停：学术墨水蓝内发光 + 微位移 */
.file-index-card:hover {
  box-shadow:
    inset 0 0 24px rgba(11, 37, 61, 0.06),
    0 2px 8px rgba(79, 60, 43, 0.04);
  border-color: rgba(11, 37, 61, 0.15);
  transform: translateY(-1px);
}

.file-index-card.processing {
  opacity: 0.8;
}

/* ── 几何图标区 ── */
.file-geometry {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: rgba(11, 37, 61, 0.03);
  border: 0.5px solid rgba(11, 37, 61, 0.08);
  border-radius: 2px;
}

/* ── 文件信息 ── */
.file-info {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-family: var(--font-serif);
  font-size: 14px;
  font-weight: 400;
  color: var(--ink-brown);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 5px;
  letter-spacing: 0.2px;
}

.file-meta {
  display: flex;
  align-items: center;
  gap: 0;
  font-size: 12px;
  color: var(--text-tertiary);
}

.meta-item {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0;
}

.meta-divider {
  margin: 0 6px;
  color: var(--border-color);
  font-family: var(--font-serif);
}

.meta-item.status.ready { color: var(--ink-brown-lighter); }
.meta-item.status.processing { color: var(--slate-blue-darker); }
.meta-item.status.pending { color: var(--ink-brown-lighter); }
.meta-item.status.error { color: var(--error-color); }

.pulse-indicator {
  display: inline-block;
  width: 5px;
  height: 5px;
  border-radius: 2px;
  background: var(--slate-blue-dark);
  margin-right: 4px;
  animation: cabinet-pulse 1.5s step-end infinite;
  vertical-align: middle;
}

@keyframes cabinet-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.25; }
}

/* 错误提示 */
.file-error {
  margin-top: 5px;
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--error-color);
  background: rgba(196, 85, 77, 0.04);
  padding: 3px 8px;
}

/* ── 操作按钮 ── */
.file-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.action-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: all var(--duration-fast) step-end;
  border-radius: 0;
}

.action-btn:hover {
  color: var(--ink-brown);
  background: rgba(11, 37, 61, 0.04);
}

/* ── TransitionGroup 动画 ── */
.file-list-enter-active,
.file-list-leave-active {
  transition: all var(--duration-normal) step-end;
}

.file-list-enter-from {
  opacity: 0;
  transform: translateX(-8px);
}

.file-list-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

.file-list-move {
  transition: transform var(--duration-normal) step-end;
}

/* ── 响应式 ── */
@media (max-width: 768px) {
  .files-container {
    padding: var(--space-5) var(--space-4);
  }

  .file-index-card {
    flex-wrap: wrap;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
  }

  .file-actions {
    width: 100%;
    justify-content: flex-end;
    padding-top: var(--space-2);
    border-top: 0.5px solid rgba(79, 60, 43, 0.04);
  }

  .file-meta {
    flex-wrap: wrap;
  }
}
</style>
