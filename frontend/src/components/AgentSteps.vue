<template>
  <div ref="cardRef" class="terminal-card" :class="{ 'tv-powered-off': !expanded }">
    <!-- 物理开关 — 边框右下角常驻 -->
    <button
      v-if="showWriteDown"
      class="physical-write-btn"
      @click="toggleExpand"
    >
      <template v-if="expanded">∴ 写在纸上</template>
      <template v-else>
        <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><line x1="7" y1="9" x2="15" y2="9"/><line x1="7" y1="12" x2="11" y2="12"/></svg>
        推理过程
      </template>
    </button>

    <div class="terminal-screen">
      <!-- 荧幕标题栏（固定） -->
      <div class="terminal-header">
        <div class="terminal-title">
          <span class="title-text">
            <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><line x1="7" y1="9" x2="15" y2="9"/><line x1="7" y1="12" x2="11" y2="12"/></svg>
            ReAct · 推理过程
          </span>
          <span class="step-badge">{{ steps.length }}</span>
        </div>
        <div class="terminal-actions">
          <span v-if="streaming" class="streaming-indicator">
            <span class="pulse-dot"></span>RUN
          </span>
        </div>
      </div>

      <!-- 步骤列表（可滚动荧幕内容） -->
      <div ref="bodyRef" class="terminal-body">
        <Transition name="tv-off" @after-leave="onTvOffDone" @after-enter="$emit('tvOnDone')">
          <div v-if="expanded" class="terminal-body-inner">
            <div
              v-for="(step, index) in formattedSteps"
              :key="index"
              class="step-line"
              :class="[step.type, { 'step-latest': index === formattedSteps.length - 1 && streaming }]"
            >
              <span class="step-prefix">
                <span class="prefix-icon" :class="step.type">
                  <svg v-if="step.type === 'thought'" xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M7 6 L17 6 L12 12 L17 18 L7 18 L12 12 Z"></path></svg>
                  <svg v-else-if="step.type === 'action'" xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path></svg>
                  <svg v-else-if="step.type === 'observation'" xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                  <svg v-else xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                </span>
                <span class="prefix-label">{{ stepLabel(step.type) }}</span>
              </span>

              <template v-if="step.type === 'thought'">
                <span class="step-body">{{ step.content }}</span>
              </template>

              <template v-else-if="step.type === 'action'">
                <span class="step-tool">
                  <span class="tool-fn">{{ step.tool }}</span>
                  <span class="tool-paren">(</span>
                  <span v-for="(value, key, i) in step.input" :key="key">
                    <span class="tool-arg">{{ key }}</span>=<span class="tool-val">{{ formatArg(value) }}</span>
                    <span v-if="i < Object.keys(step.input).length - 1" class="tool-comma">, </span>
                  </span>
                  <span class="tool-paren">)</span>
                </span>
              </template>

              <template v-else-if="step.type === 'observation'">
                <span class="step-body obs" :class="{ error: !step.success }">{{ step.content }}</span>
              </template>

              <template v-else>
                <span class="step-body system-msg">{{ step.content }}</span>
              </template>
            </div>
          </div>
        </Transition>
      </div>

      <!-- 关机摘要（固定于荧幕底部） -->
      <div v-if="!expanded" class="terminal-summary" @click="toggleExpand">
        <span
          v-for="(count, type) in stepCounts"
          :key="type"
          class="summary-chip"
          :class="type"
        >
          <span class="chip-dot"></span>
          {{ stepLabel(type) }} ×{{ count }}
        </span>
        <span v-if="streaming" class="pulse-dot"></span>
      </div>
    </div>

    <!-- 物理标签 — 底部居中凹陷 P-37 Δ -->
    <div class="bezel-label">
      <span class="label-model">P-37</span>
      <span class="label-delta">Δ</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'

const props = defineProps({
  steps: { type: Array, default: () => [] },
  streaming: { type: Boolean, default: false },
  hasAnswer: { type: Boolean, default: false }
})

const emit = defineEmits(['tvOffDone', 'tvOnDone'])

const expanded = ref(true)
const cardRef = ref(null)
const bodyRef = ref(null)

function onTvOffDone() {
  emit('tvOffDone')
  nextTick(() => {
    const summary = cardRef.value?.querySelector('.terminal-summary')
    if (summary) {
      summary.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  })
}

function scrollToBottom() {
  nextTick(() => {
    if (bodyRef.value) {
      bodyRef.value.scrollTop = bodyRef.value.scrollHeight
    }
  })
}

watch(() => props.steps.length, () => scrollToBottom())

const formattedSteps = computed(() => {
  return props.steps.map(step => {
    if (step.type) return step
    if (step.thought) return { type: 'thought', content: step.thought }
    if (step.action) return { type: 'action', tool: step.action, input: step.action_input || {} }
    if (step.observation !== undefined) {
      return {
        type: 'observation',
        content: typeof step.observation === 'object'
          ? JSON.stringify(step.observation, null, 2)
          : String(step.observation),
        success: step.observation?.success !== false
      }
    }
    return step
  })
})

const stepCounts = computed(() => {
  const counts = {}
  formattedSteps.value.forEach(s => { counts[s.type] = (counts[s.type] || 0) + 1 })
  return counts
})

const showWriteDown = computed(() => {
  return props.hasAnswer || (!props.streaming && formattedSteps.value.length > 0)
})

function toggleExpand() {
  expanded.value = !expanded.value
}

function stepLabel(type) {
  const map = { thought: '思考', action: '工具', observation: '观察', system: '系统' }
  return map[type] || type
}

function formatArg(value) {
  if (typeof value === 'object') return JSON.stringify(value)
  if (typeof value === 'string' && value.length > 60) return `"${value.substring(0, 60)}..."`
  if (typeof value === 'string') return `"${value}"`
  return value
}
</script>

<style scoped>
/* ══════════════════════════════════════
   工业 CRT 显示器 — 厚重塑料外壳 + 磷光绿单色荧幕
   ══════════════════════════════════════ */

/* ── 外壳（Bezel）── 工业米灰 ABS 塑料，钝感圆角，三层边框 ── */
.terminal-card {
  position: relative;
  /* 基色：工业米灰 + ABS 颗粒噪点滤镜 */
  background:
    repeating-linear-gradient(
      0deg,
      transparent,
      transparent 2px,
      rgba(0,0,0,0.010) 2px,
      rgba(0,0,0,0.010) 3px
    ),
    repeating-linear-gradient(
      90deg,
      transparent,
      transparent 3px,
      rgba(0,0,0,0.005) 3px,
      rgba(0,0,0,0.005) 4px
    ),
    linear-gradient(
      172deg,
      #DCD8CF 0%,
      #D1CDC4 30%,
      #C4BFB4 65%,
      #B5B0A5 100%
    );
  border-radius: 16px;
  padding: 30px;
  margin-bottom: var(--space-37);
  filter: contrast(1.06) brightness(0.97);
  /* 三层边框系统：外沿 → 斜面 → 内凹槽 */
  border: 1px solid rgba(160,155,145,0.5);
  box-shadow:
    /* L1 外沿：亮色细线（光线擦过外壳外缘） */
    0 0 0 2px rgba(180,175,165,0.45),
    /* L2 外沿阴影环 */
    0 0 0 3px rgba(0,0,0,0.05),
    /* L3 顶左斜面高光 */
    inset 2px 2px 0 rgba(255,255,255,0.32),
    /* L4 底右斜面阴影 */
    inset -2px -2px 0 rgba(0,0,0,0.10),
    /* L5 斜面过渡 — 高光侧 */
    inset 4px 4px 12px rgba(255,255,255,0.10),
    /* L6 斜面过渡 — 阴影侧 */
    inset -4px -4px 12px rgba(0,0,0,0.08),
    /* L7 荧幕凹槽深陷（内凹槽层级） */
    inset 30px 30px 55px -28px rgba(0,0,0,0.35),
    /* L8 外部投影 */
    4px 6px 16px rgba(0,0,0,0.14),
    8px 12px 30px rgba(0,0,0,0.07);
}

/* ── 物理侧按键 — 旧式打印机凹陷按钮，火漆印章质感 ── */
.physical-write-btn {
  position: absolute;
  bottom: 6px;
  right: 26px;
  padding: 3px 10px;
  background:
    linear-gradient(180deg, #C5C0B5 0%, #B8B3A7 40%, #BFBAAE 100%);
  border: 0.5px solid #A09A8E;
  border-radius: 8px;
  font-family: 'Courier', 'Courier New', monospace;
  font-size: 9px;
  color: #4A3C2B;
  cursor: pointer;
  letter-spacing: 0.3px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  box-shadow:
    /* 凹陷上沿 — 壳体阴影盖住按钮上部 */
    inset 0 2px 3px rgba(0,0,0,0.13),
    /* 凹陷下沿 — 底部内侧高光 */
    inset 0 -1px 1px rgba(255,255,255,0.30),
    /* 按钮外缘壳体贴合阴影 */
    0 1px 0 rgba(255,255,255,0.35),
    0 -0.5px 0 rgba(0,0,0,0.04);
  transition: all 0.1s step-end;
  z-index: 5;
}

.physical-write-btn:active {
  box-shadow:
    inset 0 3px 5px rgba(0,0,0,0.18),
    inset 0 -0.5px 0 rgba(255,255,255,0.15),
    0 0.5px 0 rgba(255,255,255,0.20);
  transform: translateY(1.5px);
}

/* ── 荧幕（定高视窗）── 玻璃内凹 + 磷光微染 + CRT 曲面 ── */
.terminal-screen {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 500px;
  background: var(--terminal-bg);
  border: 0.5px solid #9A9488;
  border-radius: 8px;
  overflow: hidden;
  font-family: 'Courier', 'Courier New', monospace;
  box-shadow:
    /* 第一层：深黑大模糊 — 荧幕边缘沉入塑料深处 */
    inset 0 0 50px 20px rgba(0,0,0,0.62),
    /* 第二层：极细亮色描边 — 光线打在塑料内切面上的高光 */
    inset 1px 1px 1px rgba(255,255,255,0.10),
    inset -1px -1px 1px rgba(0,0,0,0.06),
    /* 第三层：顶部光线掠过凹槽上沿 */
    inset 0 5px 14px rgba(0,0,0,0.52),
    /* 第四层：底部内阴影 */
    inset 0 -5px 14px rgba(0,0,0,0.42),
    /* 磷光绿对内斜面微光染色 */
    inset 0 0 100px 28px rgba(0,255,65,0.03);
}

/* ── 物理标签 — 底部居中凹陷压印 P-37 Δ ── */
.bezel-label {
  position: absolute;
  bottom: 8px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: baseline;
  gap: 5px;
  font-family: 'Courier New', monospace;
  font-size: 8px;
  letter-spacing: 1px;
  user-select: none;
  z-index: 2;
  color: #9A9488;
  text-shadow:
    0 1px 0 rgba(255,255,255,0.28),
    0 -0.5px 0 rgba(0,0,0,0.08);
}

.label-model {
  font-weight: 700;
  letter-spacing: 1.5px;
}

.label-delta {
  font-size: 9px;
  font-weight: 400;
}

/* 扫描线纹理（固定不动） */
.terminal-screen::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 4;
  background: repeating-linear-gradient(
    to bottom,
    transparent 0px,
    transparent 2px,
    rgba(0, 0, 0, 0.03) 2px,
    rgba(0, 0, 0, 0.03) 4px
  );
}

/* CRT 玻璃曲面 — 径向渐变模拟老式显像管微凸、四周略暗 */
.terminal-screen::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 3;
  border-radius: 8px;
  background: radial-gradient(
    ellipse at 50% 45%,
    transparent 50%,
    rgba(0,0,0,0.04) 70%,
    rgba(0,0,0,0.15) 100%
  );
}

/* ── 荧幕标题栏（固定）── */
.terminal-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 6px 24px;
  background: rgba(0,0,0,0.15);
  border-bottom: 0.5px solid rgba(0,255,65,0.08);
  user-select: none;
  position: relative;
  z-index: 1;
  flex-shrink: 0;
}

.terminal-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.title-text {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: 400;
  color: #00FF41;
  letter-spacing: 0;
  text-shadow: 0 0 4px rgba(0,255,65,0.25);
}

.step-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  font-size: 10px;
  font-weight: 400;
  color: #00FF41;
  background: rgba(0,255,65,0.06);
  border-radius: 0;
  text-shadow: 0 0 3px rgba(0,255,65,0.20);
}

.terminal-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.streaming-indicator {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 10px;
  color: #00FF41;
  text-shadow: 0 0 4px rgba(0,255,65,0.30);
}

.pulse-dot {
  width: 5px;
  height: 5px;
  background: #00FF41;
  border-radius: 50%;
  animation: terminal-pulse 1.2s step-end infinite;
}

@keyframes terminal-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.2; }
}

/* ── 荧幕内容区（可滚动视窗）── */
.terminal-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 24px;
  position: relative;
  z-index: 1;
  scrollbar-width: thin;
  scrollbar-color: #4A4540 transparent;
}

.terminal-body-inner {
  min-height: 100%;
  transform-origin: center center;
}

/* ── TV-off / TV-on 转场动画 ── */
.tv-off-enter-active {
  animation: tv-expand 0.30s ease-out forwards;
}

.tv-off-leave-active {
  animation: tv-collapse 0.35s ease-in forwards;
  overflow: hidden;
}

@keyframes tv-collapse {
  0%   { transform: scale(1, 1); opacity: 1; filter: brightness(1); }
  30%  { transform: scale(1, 0.04); opacity: 0.9; filter: brightness(1.5); }
  60%  { transform: scale(0.04, 0.04); opacity: 0.5; filter: brightness(2.5); }
  100% { transform: scale(0, 0); opacity: 0; filter: brightness(4); }
}

@keyframes tv-expand {
  0%   { transform: scale(0.04, 0.04); opacity: 0; filter: brightness(3); }
  50%  { transform: scale(0.04, 1); opacity: 0.6; filter: brightness(1.3); }
  100% { transform: scale(1, 1); opacity: 1; filter: brightness(1); }
}

.terminal-body::-webkit-scrollbar {
  width: 5px;
}

.terminal-body::-webkit-scrollbar-track {
  background: transparent;
}

.terminal-body::-webkit-scrollbar-thumb {
  background: #4A4540;
  border-radius: 0;
}

/* ── 收起摘要（固定于荧幕底部）── */
.terminal-summary {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 6px 24px;
  background: rgba(0,255,65,0.03);
  border-top: 0.5px solid rgba(0,255,65,0.08);
  font-size: 11px;
  cursor: pointer;
  transition: background 0.1s step-end;
  position: relative;
  z-index: 1;
  flex-shrink: 0;
}

/* ── 步骤行 ── */
.step-line {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 4px 0;
  font-size: 12px;
  line-height: 1.7;
  border-left: 1px solid rgba(0,255,65,0.18);
  padding-left: 10px;
  margin-bottom: 1px;
  animation: step-fade-in 0.2s step-end;
}

@keyframes step-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.step-latest {
  background: rgba(0,255,65,0.02);
}

/* ── 步骤前缀 ── */
.step-prefix {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
  min-width: 46px;
  padding-top: 1px;
}

/* ── 步骤内容 — 全部单色磷光绿 + 辉光 ── */
.step-body {
  color: #00FF41;
  word-break: break-word;
  flex: 1;
  min-width: 0;
  text-shadow: 0 0 3px rgba(0,255,65,0.15);
}

.step-body.obs {
  color: #00FF41;
  white-space: pre-wrap;
  max-height: 180px;
  overflow-y: auto;
}

.step-body.obs.error {
  color: #00FF41;
  text-decoration: underline;
}

.step-body.system-msg {
  color: #00FF41;
}

/* ── 工具调用 — 全部单色磷光绿 ── */
.step-tool {
  color: #00FF41;
  word-break: break-word;
}

.tool-fn {
  color: #00FF41;
  font-weight: 700;
  text-shadow: 0 0 3px rgba(0,255,65,0.20);
}

.tool-paren { color: #00FF41; }
.tool-arg   { color: #00FF41; }
.tool-val   { color: #00FF41; }
.tool-comma { color: #00FF41; }

/* ── 步骤前缀 ── */
.prefix-label {
  font-size: 10px;
  font-weight: 600;
  color: #00FF41;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  text-shadow: 0 0 3px rgba(0,255,65,0.18);
}

.prefix-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 0;
  color: #00FF41;
  background: rgba(0,255,65,0.06);
}

.summary-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 0;
  font-weight: 500;
  color: #00FF41;
  background: rgba(0,255,65,0.05);
  text-shadow: 0 0 3px rgba(0,255,65,0.18);
}

.chip-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #00FF41;
}
</style>
