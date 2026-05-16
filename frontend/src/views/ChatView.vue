<template>
  <div class="chat-layout">
    <!-- ── 索引卡片（散落在左侧） ── -->
    <aside class="index-cards">
      <button class="index-new-proof" @click="createNewChat">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        New Proof
      </button>
      <div
        v-for="conv in chatStore.conversations"
        :key="conv.id"
        class="index-card"
        :class="{ active: conv.id === chatStore.currentConversationId }"
        @click="loadConversation(conv.id)"
      >
        <svg class="conv-icon" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
        <span class="conv-title">{{ conv.title || '新对话' }}</span>
      </div>
    </aside>

    <!-- ── 右侧聊天区 ── -->
    <div class="chat-main">
      <!-- 文件选择栏（只读用户） -->
      <div v-if="userStore.isReadonly" class="file-selection-bar">
        <div class="selection-label">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m22 7-8.991 5.727a2 2 0 0 1-2.009 0L2 7"></path><rect x="2" y="4" width="20" height="16" rx="2"></rect></svg>
          选择要分析的文件
        </div>
        <div class="selected-files">
          <span v-for="file in selectedFilesInfo" :key="file.id" class="selected-file-tag">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"></path><path d="M14 2v4a2 2 0 0 0 2 2h4"></path></svg>
            {{ file.name }}
            <button class="remove-btn" @click.stop="toggleFile(file.id)" aria-label="移除文件">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg>
            </button>
          </span>
          <button v-if="!showFileSelector" class="add-file-btn" @click="showFileSelector = true">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"></path><path d="M12 5v14"></path></svg>
            选择文件
          </button>
        </div>

        <Teleport to="body">
          <div v-if="showFileSelector" class="file-selector-overlay" @click.self="showFileSelector = false">
            <div class="file-selector-popup">
              <div class="file-selector-header">
                <h4>选择文件</h4>
                <button class="close-btn" @click="showFileSelector = false" aria-label="关闭">
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg>
                </button>
              </div>
              <div class="file-list">
                <label v-for="file in availableFiles" :key="file.id" class="file-option" :class="{ selected: tempSelectedFiles.includes(file.id) }">
                  <input type="checkbox" :value="file.id" v-model="tempSelectedFiles" />
                  <span class="checkbox-custom">
                    <svg v-if="tempSelectedFiles.includes(file.id)" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                  </span>
                  <svg class="file-icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"></path><path d="M14 2v4a2 2 0 0 0 2 2h4"></path></svg>
                  <span class="file-name">{{ file.name }}</span>
                </label>
                <div v-if="availableFiles.length === 0" class="empty-files">
                  <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"></path><path d="M14 2v4a2 2 0 0 0 2 2h4"></path></svg>
                  <p>暂无文件，请先上传</p>
                </div>
              </div>
              <div class="file-selector-actions">
                <button class="btn btn-secondary" @click="showFileSelector = false">取消</button>
                <button class="btn btn-primary" @click="confirmFileSelection">确定 ({{ tempSelectedFiles.length }})</button>
              </div>
            </div>
          </div>
        </Teleport>
      </div>

      <!-- ── 消息区域 ── -->
      <div ref="messagesContainer" class="messages-area">
        <!-- 欢迎面板 -->
        <!-- ═══ 欢迎面板 ═══ -->
        <div v-if="chatStore.messages.length === 0" class="welcome-panel">
          <!-- 沙漏双三角印章 -->
          <div class="stamp-block">
            <svg xmlns="http://www.w3.org/2000/svg" width="72" height="72" viewBox="0 0 72 72" fill="none">
              <path d="M18 14 L54 14 L36 34" stroke="#4F3C2B" stroke-width="0.5" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M18 58 L54 58 L36 38" stroke="#4F3C2B" stroke-width="0.5" stroke-linecap="round" stroke-linejoin="round"/>
              <circle cx="36" cy="36" r="1.2" fill="#4F3C2B"/>
            </svg>
          </div>

          <h2 class="welcome-title">我是你的数据分析助手 <em class="highlight">37</em></h2>

          <div class="quick-cards">
            <div class="academic-card" @click="sendQuick('帮我分析已上传文件的数据')">
              <div class="card-icon">
                <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 28 28" fill="none" stroke="#4F3C2B" stroke-width="0.5" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="23" x2="24" y2="23"/><line x1="4" y1="23" x2="4" y2="4"/><line x1="3" y1="18" x2="5" y2="18"/><line x1="3" y1="13" x2="5" y2="13"/><line x1="3" y1="8" x2="5" y2="8"/><circle cx="9" cy="17" r="0.8"/><circle cx="13" cy="14" r="0.8"/><circle cx="17" cy="11" r="0.8"/><circle cx="20" cy="8" r="0.8"/></svg>
              </div>
              <h3 class="card-title">数据探索</h3>
              <p class="card-desc">上传 CSV / Excel，37 会自主发现规律与异常</p>
            </div>
            <div class="academic-card" @click="sendQuick('帮我编写 Python 代码进行统计分析')">
              <div class="card-icon">
                <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 28 28" fill="none" stroke="#4F3C2B" stroke-width="0.5" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="22" x2="25" y2="22"/><line x1="3" y1="22" x2="3" y2="5"/><path d="M5 16 Q9 5, 14 10 Q18 13, 22 7"/></svg>
              </div>
              <h3 class="card-title">智能分析</h3>
              <p class="card-desc">AI 代理编写代码，实时展示推理与计算过程</p>
            </div>
            <div class="academic-card" @click="sendQuick('请根据数据生成一份分析报告')">
              <div class="card-icon">
                <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 28 28" fill="none" stroke="#4F3C2B" stroke-width="0.5" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="22" x2="25" y2="22"/><line x1="3" y1="22" x2="3" y2="5"/><path d="M5 19 Q8 19, 10 14 Q12 9, 14 7 Q16 5, 17 9 Q18 13, 20 17 Q22 20, 24 19"/></svg>
              </div>
              <h3 class="card-title">洞察报告</h3>
              <p class="card-desc">基于严谨数学方法，提炼可读性极强的结论</p>
            </div>
          </div>
        </div>

        <!-- 消息列表 -->
        <template v-else>
          <div
            v-for="message in chatStore.messages"
            :key="message.id"
            class="message-item"
            :class="message.role"
          >
            <!-- 用户消息 -->
            <div v-if="message.role === 'user'" class="user-message">{{ message.content }}</div>

            <!-- AI 消息 -->
            <div v-else class="ai-message">
              <AgentSteps
                v-if="message.steps && message.steps.length > 0"
                :steps="message.steps"
                :has-answer="!!message.content"
                @tv-off-done="handleTvOff(message.id)"
                @tv-on-done="handleTvOn(message.id)"
              />
              <div v-if="message.content" class="answer-paper" :class="{ 'paper-rise': risingPapers.has(message.id) }">
                <div class="paper-stack">
                  <div class="answer-text" v-html="renderMarkdown(message.content)"></div>
                </div>
              </div>
            </div>

            <div class="message-time">{{ formatTime(message.timestamp) }}</div>
          </div>
        </template>

        <!-- 正在输入指示器 -->
        <div v-if="chatStore.isStreaming" class="typing-indicator">
          <AgentSteps :steps="chatStore.agentSteps" :streaming="true" />
        </div>
      </div>

      <!-- ── 输入区域 ── -->
      <div class="input-area">
        <div class="input-wrapper" :class="{ disabled: userStore.isReadonly && chatStore.selectedFiles.length === 0 }">
          <textarea
            v-model="inputMessage"
            :placeholder="inputPlaceholder"
            rows="1"
            @keydown.enter.prevent="sendMessage"
            @input="autoResize"
            ref="inputRef"
            :disabled="userStore.isReadonly && chatStore.selectedFiles.length === 0"
          ></textarea>
          <button
            class="send-btn"
            :disabled="!canSend"
            @click="sendMessage"
            :class="{ 'is-loading': chatStore.isStreaming }"
          >
            <span v-if="chatStore.isStreaming" class="loading-spinner"></span>
            <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 4 L20 18 L4 18 Z"/></svg>
          </button>
        </div>
        <div class="input-tips">
          <span v-if="userStore.isReadonly" class="tip readonly">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M12 16v-4"></path><path d="M12 8h.01"></path></svg>
            请先选择文件，AI 将只分析选定的文件
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useChatStore } from '@/stores/chat'
import { filesApi } from '@/api/files'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import AgentSteps from '@/components/AgentSteps.vue'

const userStore = useUserStore()
const chatStore = useChatStore()
const route = useRoute()
const router = useRouter()

const inputMessage = ref('')
const inputRef = ref(null)
const messagesContainer = ref(null)
const showFileSelector = ref(false)
const availableFiles = ref([])
const tempSelectedFiles = ref([])
const risingPapers = ref(new Set())

function handleTvOff(messageId) {
  risingPapers.value.add(messageId)
}

function handleTvOn(messageId) {
  risingPapers.value.delete(messageId)
}

const canSend = computed(() => inputMessage.value.trim() && !chatStore.isStreaming)

const inputPlaceholder = computed(() => {
  if (userStore.isReadonly && chatStore.selectedFiles.length === 0) return '请先选择要分析的文件...'
  return '输入你的问题...（例如：分析销售数据的趋势）'
})

const selectedFilesInfo = computed(() => {
  return availableFiles.value.filter(f => chatStore.selectedFiles.includes(f.id))
})

function autoResize() {
  const textarea = inputRef.value
  textarea.style.height = 'auto'
  textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px'
}

async function sendMessage() {
  if (!canSend.value) return
  const message = inputMessage.value.trim()
  inputMessage.value = ''
  nextTick(autoResize)
  if (userStore.isReadonly && chatStore.selectedFiles.length === 0) {
    alert('请先选择要分析的文件')
    return
  }
  await chatStore.sendMessageStream(message, {}, () => scrollToBottom())
  scrollToBottom()
}

function sendQuick(text) { inputMessage.value = text; sendMessage() }
function createNewChat() {
  chatStore.createNewConversation()
  router.push('/')
}
function loadConversation(id) {
  chatStore.loadConversation(id)
  router.push(`/conversation/${id}`)
}
function toggleFile(fileId) { chatStore.toggleFileSelection(fileId) }
function confirmFileSelection() { chatStore.selectedFiles = [...tempSelectedFiles.value]; showFileSelector.value = false }

function renderMarkdown(text) {
  if (!text) return ''
  return DOMPurify.sanitize(marked.parse(text, { breaks: true }))
}

function formatTime(timestamp) {
  if (!timestamp) return ''
  return new Date(timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  })
}

async function loadFiles() {
  try {
    const res = await filesApi.getList()
    availableFiles.value = res.data || []
  } catch (error) { console.error('加载文件失败:', error) }
}

async function loadConversations() {
  await chatStore.fetchConversations()
}

function onFilesUpdated() {
  loadFiles()
}

onMounted(() => {
  loadFiles()
  loadConversations()
  const conversationId = route.params.id
  if (conversationId) {
    chatStore.loadConversation(Number(conversationId))
  }
  window.addEventListener('files-updated', onFilesUpdated)
})

onUnmounted(() => {
  window.removeEventListener('files-updated', onFilesUpdated)
})

watch(() => route.params.id, (newId) => {
  if (newId) {
    chatStore.loadConversation(Number(newId))
  }
})
</script>

<style scoped>
.chat-layout {
  position: relative;
  display: flex;
  justify-content: center;
  min-height: calc(100vh - 56px);
  padding: 0 2rem;
}

/* ══════════════════════════════════════
   索引卡片 — 散落在左侧的白色卡纸
   ══════════════════════════════════════ */
.index-cards {
  position: absolute;
  left: 2rem;
  top: var(--space-37);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  z-index: 10;
  max-width: 210px;
}

.index-card {
  background: #FCFAF5;
  border: 0.5px solid #E0D8C0;
  border-radius: 0;
  padding: 10px 14px;
  cursor: pointer;
  box-shadow:
    2px 3px 6px rgba(79, 60, 43, 0.06),
    3px 5px 12px rgba(79, 60, 43, 0.04);
  transition: all var(--duration-fast) step-end;
  display: flex;
  align-items: center;
  gap: 8px;
}

.index-card:nth-child(1) { transform: rotate(-0.8deg); }
.index-card:nth-child(2) { transform: rotate(0.5deg); }
.index-card:nth-child(3) { transform: rotate(-0.3deg); }
.index-card:nth-child(4) { transform: rotate(1.0deg); }
.index-card:nth-child(5) { transform: rotate(-0.6deg); }

.index-card:hover {
  box-shadow:
    3px 5px 10px rgba(79, 60, 43, 0.10),
    4px 8px 18px rgba(79, 60, 43, 0.06);
  transform: translateY(-1px) rotate(0deg);
}

.index-card.active {
  box-shadow:
    3px 5px 10px rgba(79, 60, 43, 0.12),
    4px 8px 18px rgba(79, 60, 43, 0.08);
  transform: rotate(0deg);
}

.index-card .conv-icon {
  flex-shrink: 0;
  color: rgba(79, 60, 43, 0.25);
  width: 14px;
  height: 14px;
}

.index-card.active .conv-icon {
  color: rgba(79, 60, 43, 0.50);
}

.index-card .conv-title {
  font-size: 12px;
  color: rgba(79, 60, 43, 0.50);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 400;
}

.index-card.active .conv-title {
  color: rgba(79, 60, 43, 0.75);
  font-weight: 500;
}

/* New Proof 索引卡片 */
.index-new-proof {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 14px;
  background: #FCFAF5;
  border: 0.5px solid rgba(79, 60, 43, 0.12);
  border-radius: 0;
  color: var(--ink-brown);
  font-size: 12px;
  font-weight: 500;
  font-family: var(--font-sans);
  cursor: pointer;
  letter-spacing: 0.3px;
  box-shadow:
    inset 0 1px 2px rgba(79, 60, 43, 0.06),
    inset 0 -1px 2px rgba(255, 255, 255, 0.40);
  transition: all var(--duration-fast) step-end;
  transform: rotate(-0.4deg);
}

.index-new-proof:hover {
  box-shadow:
    inset 0 1px 3px rgba(79, 60, 43, 0.10),
    inset 0 -1px 2px rgba(255, 255, 255, 0.25);
  transform: translateY(-1px) rotate(0deg);
}

.index-new-proof:active {
  box-shadow:
    inset 0 1px 4px rgba(79, 60, 43, 0.14),
    inset 0 -1px 1px rgba(255, 255, 255, 0.15);
  transform: translateY(1px) rotate(0deg);
}

/* ══════════════════════════════════════
   主聊天区 — 垂直堆叠，中轴居中
   ══════════════════════════════════════ */
.chat-main {
  width: 100%;
  max-width: var(--content-width);
  display: flex;
  flex-direction: column;
}

/* ── 文件选择栏 ── */
.file-selection-bar {
  background: var(--parchment-light);
  border-bottom: 0.5px solid #E0D8C0;
  padding: var(--space-3) var(--space-5);
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.selection-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
  font-weight: 500;
}

.selected-files {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  flex: 1;
}

.selected-file-tag {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 3px 8px 3px 10px;
  background: var(--parchment);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--ink-brown);
  font-weight: 500;
}

.selected-file-tag .remove-btn {
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 2px;
  border-radius: 2px;
  color: var(--ink-brown-light);
  display: flex;
  align-items: center;
  transition: all var(--duration-fast) ease;
}

.selected-file-tag .remove-btn:hover {
  color: var(--error-color);
}

.add-file-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: 3px 10px;
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  font-family: var(--font-sans);
  transition: all var(--duration-fast) ease;
}

.add-file-btn:hover {
  border-color: var(--slate-blue-dark);
  color: var(--ink-brown);
}

/* ── 文件选择弹窗 ── */
.file-selector-overlay {
  position: fixed;
  inset: 0;
  background: rgba(58,40,24,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  animation: fadeIn var(--duration-fast) var(--ease-out);
}

@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

.file-selector-popup {
  background: var(--parchment-light);
  border: 0.5px solid #D4C9A8;
  border-radius: var(--radius-md);
  width: 100%;
  max-width: 400px;
  margin: var(--space-4);
  animation: slideUp var(--duration-normal) var(--ease-out);
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(20px); }
  to   { opacity: 1; transform: translateY(0); }
}

.file-selector-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-4) 0;
}

.file-selector-header h4 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.close-btn {
  border: none;
  background: none;
  cursor: pointer;
  padding: var(--space-1);
  border-radius: var(--radius-sm);
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  transition: all var(--duration-fast) ease;
}

.close-btn:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.file-list {
  max-height: 280px;
  overflow-y: auto;
  padding: var(--space-3) var(--space-4);
}

.file-option {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: all var(--duration-fast) ease;
}

.file-option:hover { background: var(--surface-hover); }
.file-option.selected { background: var(--parchment-dark); }

.file-option input[type="checkbox"] {
  position: absolute; opacity: 0; width: 0; height: 0;
}

.checkbox-custom {
  width: 16px; height: 16px;
  border: 1px solid var(--border-color);
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--duration-fast) ease;
  flex-shrink: 0;
}

.file-option.selected .checkbox-custom {
  background: var(--ink-brown);
  border-color: var(--ink-brown);
  color: var(--parchment-light);
}

.file-icon { color: var(--slate-blue-darker); flex-shrink: 0; }

.file-name {
  font-size: 14px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.empty-files {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-8);
  color: var(--text-tertiary);
  text-align: center;
}

.empty-files p { margin-top: var(--space-3); font-size: 14px; }

.file-selector-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4) var(--space-4);
  border-top: 1px solid var(--border-light);
}

/* ══════════════════════════════════════
   消息区域
   ══════════════════════════════════════ */
.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-5);
}

/* ═══ 欢迎面板 ═══ */
.welcome-panel {
  text-align: center;
  padding: 100px 40px 80px;
  max-width: var(--content-width);
  margin: 0 auto;
}

/* ── 37 沙漏印章 ── */
.stamp-block {
  margin: 0 auto 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.85;
}

.welcome-title {
  font-family: Georgia, 'Crimson Text', 'Times New Roman', serif;
  font-size: 24px;
  font-weight: 400;
  color: var(--ink-brown);
  margin-top: 40px;
  margin-bottom: 40px;
  letter-spacing: 0.2px;
  line-height: 1.6;
}

.welcome-title .highlight {
  font-family: Georgia, 'Crimson Text', 'Times New Roman', serif;
  font-style: italic;
  font-weight: 700;
  font-size: 28px;
  color: #AFD5E1;
}

/* ── 学术功能卡片 ── */
.quick-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  max-width: var(--content-width);
  margin: 8px auto 0;
}

.academic-card {
  padding: 24px 18px 20px;
  background: var(--parchment-light);
  border: 0.5px solid #E0D8C0;
  border-radius: 4px;
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
  text-align: center;
}

.academic-card:hover {
  transform: translateY(-2px);
  border-color: #B0A080;
}

.card-icon {
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.7;
}

.card-title {
  font-family: Georgia, 'Crimson Text', 'Times New Roman', serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--ink-brown);
  margin-bottom: 8px;
  letter-spacing: 0.2px;
}

.card-desc {
  font-family: var(--font-sans);
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.6;
  margin: 0;
}

/* ── 消息项 ── */
.message-item {
  margin-bottom: var(--space-5);
  max-width: var(--content-width);
  animation: messageSlideIn var(--duration-normal) var(--ease-out);
}

@keyframes messageSlideIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.message-item.user {
  margin-left: auto;
}

/* 用户消息气泡 */
.user-message {
  background: #FAF6E8;
  border: 0.5px solid #E0D8C0;
  color: var(--ink-brown);
  padding: var(--space-3) var(--space-4);
  border-radius: 6px;
  border-bottom-right-radius: 2px;
  font-size: 14px;
  line-height: 1.6;
  font-family: var(--font-sans);
}

/* AI 消息 - 无背景包裹，由终端卡片和叠纸卡片各自独立 */
.ai-message {
  border-radius: 0;
  overflow: visible;
}

/* ── 叠纸答案卡片 ── */
.answer-paper {
  position: relative;
  margin-top: var(--space-2);
}

.answer-paper.paper-rise {
  animation: paperRise 0.5s var(--ease-out) both;
}

@keyframes paperRise {
  from { opacity: 0.7; transform: translateY(16px); }
  to   { opacity: 1;   transform: translateY(0); }
}

.paper-stack {
  position: relative;
  background: #FAF6E8;
  border: 0.5px solid #E0D8C0;
  border-radius: 4px;
  padding: 28px 32px;
}

.paper-stack::before {
  content: '';
  position: absolute;
  inset: -3px -3px -6px -3px;
  background: #F7F2E0;
  border: 0.5px solid #E8E0C0;
  border-radius: 4px;
  z-index: -2;
  transform: rotate(-0.2deg);
}

.paper-stack::after {
  content: '';
  position: absolute;
  inset: -6px -6px -10px -6px;
  background: #F2ECD4;
  border: 0.5px solid #E8E0C0;
  border-radius: 4px;
  z-index: -3;
  transform: rotate(0.3deg);
}

.answer-text {
  font-family: var(--font-serif);
  font-size: 15px;
  line-height: 1.9;
  color: var(--ink-brown);
}

.answer-text :deep(p) {
  margin-bottom: var(--space-3);
  text-align: justify;
}

.answer-text :deep(p:last-child) { margin-bottom: 0; }

.answer-text :deep(h1),
.answer-text :deep(h2),
.answer-text :deep(h3) {
  font-family: var(--font-serif);
  color: var(--ink-brown-dark);
  margin-top: var(--space-5);
  margin-bottom: var(--space-3);
  font-weight: 600;
}

.answer-text :deep(h2) { font-size: 18px; }
.answer-text :deep(h3) { font-size: 16px; }

.answer-text :deep(strong) {
  color: var(--ink-brown-dark);
  font-weight: 600;
}

.answer-text :deep(code) {
  background: var(--parchment-dark);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--ink-brown);
}

.answer-text :deep(pre) {
  background: var(--terminal-bg);
  color: var(--terminal-text);
  padding: var(--space-4);
  border-radius: 2px;
  border: 0.5px solid var(--terminal-border);
  overflow-x: auto;
  margin: var(--space-3) 0;
  font-family: var(--font-mono);
  font-size: 12px;
}

.answer-text :deep(pre code) {
  background: transparent;
  color: inherit;
  padding: 0;
}

.answer-text :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: var(--space-3) 0;
  font-size: 13px;
  font-family: var(--font-sans);
}

.answer-text :deep(th),
.answer-text :deep(td) {
  border: 1px solid var(--border-color);
  padding: var(--space-2) var(--space-3);
  text-align: left;
}

.answer-text :deep(th) {
  background: var(--parchment-dark);
  font-weight: 600;
  color: var(--ink-brown);
}

.answer-text :deep(tr:hover) { background: var(--parchment); }

.answer-text :deep(ul),
.answer-text :deep(ol) {
  margin: var(--space-3) 0;
  padding-left: var(--space-6);
}

.answer-text :deep(li) { margin-bottom: var(--space-1); }

.answer-text :deep(blockquote) {
  border-left: 1px solid var(--slate-blue-dark);
  padding-left: var(--space-3);
  margin: var(--space-3) 0;
  color: var(--text-secondary);
  font-style: italic;
}

.message-time {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: var(--space-1);
}

.message-item.user .message-time { text-align: right; }

/* ── 正在输入 ── */
.typing-indicator {
  max-width: var(--content-width);
  margin-bottom: var(--space-5);
  animation: messageSlideIn var(--duration-normal) var(--ease-out);
}

/* ══════════════════════════════════════
   输入区域 — 祭坛式凹槽
   ══════════════════════════════════════ */
.input-area {
  background: var(--parchment);
  border-top: none;
  padding: 20px 24px 28px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.input-wrapper {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  width: 100%;
  max-width: var(--content-width);
  background: #FBF8EB;
  border: 0.5px solid #D4C9A8;
  border-radius: 6px;
  padding: 10px 14px;
  transition: border-color var(--duration-fast) var(--ease-out),
              box-shadow var(--duration-fast) var(--ease-out);
  box-shadow: inset 0 1px 3px rgba(79, 60, 43, 0.05);
}

.input-wrapper:focus-within {
  border-color: #B0A080;
  box-shadow: inset 0 1px 4px rgba(79, 60, 43, 0.08);
}

.input-wrapper.disabled {
  opacity: 0.5;
}

.input-wrapper textarea {
  flex: 1;
  border: none;
  background: transparent;
  resize: none;
  font-size: 14px;
  line-height: 1.6;
  max-height: 120px;
  padding: 4px 0;
  font-family: var(--font-sans);
  color: var(--text-primary);
}

.input-wrapper textarea:focus { outline: none; }
.input-wrapper textarea::placeholder { color: var(--text-tertiary); }
.input-wrapper textarea:disabled { cursor: not-allowed; }

.send-btn {
  width: 32px; height: 32px;
  border: 0.5px solid #D4C9A8;
  border-radius: 3px;
  background: transparent;
  color: var(--ink-brown-light);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--duration-fast) var(--ease-out);
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  background: var(--parchment-dark);
  color: var(--ink-brown);
  border-color: #B0A080;
}

.send-btn:active:not(:disabled) { opacity: 0.7; }
.send-btn:disabled { opacity: 0.25; cursor: not-allowed; }
.send-btn.is-loading { background: transparent; }

.input-tips {
  margin-top: 10px;
  font-size: 12px;
  width: 100%;
  max-width: var(--content-width);
}

.tip {
  display: flex;
  align-items: center;
  gap: 6px;
}

.tip.readonly { color: var(--text-tertiary); }

/* ══════════════════════════════════════
   响应式
   ══════════════════════════════════════ */
@media (max-width: 768px) {
  .index-cards { display: none; }

  .message-item { max-width: 95%; }

  .quick-cards {
    grid-template-columns: 1fr;
  }

  .file-selection-bar {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-2);
  }

  .paper-stack {
    padding: var(--space-4);
  }
}
</style>
