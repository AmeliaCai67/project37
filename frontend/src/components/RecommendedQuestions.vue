<template>
  <div class="recommended-questions" v-if="questions.length">
    <div class="section-title">37 的发现</div>
    <div class="question-list">
      <button
        v-for="(q, idx) in questions"
        :key="idx"
        class="question-chip"
        @click="ask(q)"
      >
        {{ q }}
      </button>
    </div>
    <button class="refresh" @click="refresh">重新分析数据关系</button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useChatStore } from '@/stores/chat.js'

const store = useChatStore()
const questions = computed(() => store.roadmap?.questions || [])

function ask(q) {
  store.sendMessageStream(q)
}

function refresh() {
  store.fetchRoadmap()
}
</script>

<style scoped>
.recommended-questions {
  padding: 12px;
  border-bottom: 1px solid var(--ink-10);
}
.section-title {
  font-size: 12px;
  color: var(--ink-50);
  margin-bottom: 8px;
}
.question-chip {
  display: block;
  width: 100%;
  text-align: left;
  padding: 8px 12px;
  margin-bottom: 6px;
  background: var(--paper);
  border: 1px solid var(--ink-10);
  border-radius: 6px;
  cursor: pointer;
}
.question-chip:hover {
  background: var(--ink-5);
}
.refresh {
  margin-top: 8px;
  font-size: 12px;
  color: var(--blue-60);
  background: none;
  border: none;
  cursor: pointer;
}
</style>
