<template>
  <Teleport to="body">
    <div v-if="visible" class="roadmap-modal-overlay" @click.self="close">
      <div class="roadmap-modal-content">
        <button class="close-btn" @click="close" aria-label="关闭">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
        </button>

        <h3 class="modal-title">
          37 已经看过「{{ workspaceName }}」
        </h3>

        <p class="modal-summary">
          发现了 {{ tableCount }} 张表，{{ relationshipCount }} 组关系。
        </p>

        <div v-if="roadmap?.relationships?.length" class="relations">
          <div
            v-for="(rel, idx) in roadmap.relationships.slice(0, 3)"
            :key="idx"
            class="relation-item"
          >
            {{ tableName(rel.source) }} ↔ {{ tableName(rel.target) }}
          </div>
        </div>

        <div class="questions-section">
          <div class="section-label">你可以这样问：</div>
          <div class="question-list">
            <button
              v-for="(q, idx) in roadmap?.questions?.slice(0, 5)"
              :key="idx"
              class="question-btn"
              @click="ask(q)"
            >
              {{ questionText(q) }}
            </button>
          </div>
        </div>

        <label class="no-again">
          <input type="checkbox" v-model="dontShowAgain" />
          今天不再提示
        </label>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed } from 'vue'
import { stripTimestampPrefix } from '@/utils/display'

const props = defineProps({
  visible: Boolean,
  roadmap: Object,
  workspace: Object
})
const emit = defineEmits(['close', 'ask'])

const dontShowAgain = ref(false)

// 只统计表节点（不含列节点）：优先用后端 table_count，兜底 tables 长度
const tableCount = computed(() =>
  props.roadmap?.table_count ?? props.roadmap?.tables?.length ?? 0
)
const relationshipCount = computed(() => props.roadmap?.relationships?.length || 0)

const workspaceName = computed(() =>
  stripTimestampPrefix(props.workspace?.name) || '你的工作区'
)

function tableName(fullName) {
  if (!fullName) return ''
  // 边端点是 '表.列' 形式，取表名并去时间戳前缀
  const base = String(fullName).split('/').pop().split('.')[0]
  return stripTimestampPrefix(base)
}

// 兼容字符串与 {question, tables, type} 对象两种形态
function questionText(q) {
  return typeof q === 'string' ? q : q?.question || ''
}

function close() {
  if (dontShowAgain.value) {
    const key = `hide_welcome_roadmap_${new Date().toISOString().slice(0, 10)}`
    localStorage.setItem(key, '1')
  }
  emit('close')
}

function ask(q) {
  emit('ask', questionText(q))
  close()
}
</script>

<style scoped>
.roadmap-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(79, 60, 43, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.roadmap-modal-content {
  position: relative;
  /* 不透明背景，避免背后首页文字透出（曾引用未定义的 --paper） */
  background: var(--parchment-light);
  border: 0.5px solid #E0D0B0;
  border-radius: 8px;
  padding: 28px 32px;
  max-width: 520px;
  width: 90%;
  box-shadow: 0 12px 40px rgba(79, 60, 43, 0.15);
}

.close-btn {
  position: absolute;
  top: 14px;
  right: 14px;
  background: none;
  border: none;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: 4px;
}

.modal-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--ink-brown);
  margin: 0 0 8px;
}

.modal-summary {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0 0 16px;
}

.relations {
  margin-bottom: 20px;
}

.relation-item {
  font-size: 13px;
  color: var(--slate-blue-dark);
  padding: 6px 10px;
  background: var(--slate-blue-light, #f0f4f8);
  border-radius: 4px;
  margin-bottom: 6px;
}

.questions-section {
  margin-bottom: 16px;
}

.section-label {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 10px;
}

.question-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.question-btn {
  text-align: left;
  padding: 10px 14px;
  background: var(--parchment);
  border: 0.5px solid #E0D8C0;
  border-radius: 6px;
  color: var(--ink-brown);
  cursor: pointer;
  font-size: 14px;
  transition: background var(--duration-fast) var(--ease-out);
}

.question-btn:hover {
  background: var(--parchment-dark);
}

.no-again {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-tertiary);
  cursor: pointer;
}
</style>
