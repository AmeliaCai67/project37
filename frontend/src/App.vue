<template>
  <RouterView />
</template>

<script setup>
import { RouterView } from 'vue-router'
import { onMounted } from 'vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

onMounted(() => {
  userStore.fetchUserInfo()
})
</script>

<style>
/* ── Project 37 全局样式 ── */
:root {
  /* === 37 主题色板 === */
  --parchment:        #F5EFD5;
  --parchment-light:  #FBF8EB;
  --parchment-dark:   #EDE5C8;

  --ink-brown:        #4F3C2B;
  --ink-brown-light:  #7A5C3E;
  --ink-brown-lighter:#B0A080;
  --ink-brown-dark:   #3A2818;

  --slate-blue:       #AFD5E1;
  --slate-blue-dark:  #8FAFBD;
  --slate-blue-darker:#6A8A9A;
  --slate-blue-light: #C5E0EA;

  /* === 语义色 === */
  --success-color: #5A8F5A;
  --warning-color: #C4A35A;
  --error-color:   #C4554D;
  --info-color:    #6A8A9A;

  /* 语义背景 */
  --success-bg: #E8F0E4;
  --warning-bg: #F5EDD8;
  --error-bg:   #F2E0DF;
  --info-bg:    #E0ECF2;

  /* === 表面 / 背景 === */
  --bg-color:        var(--parchment);
  --surface-color:   var(--parchment-light);
  --surface-hover:   var(--parchment-dark);
  --border-color:    #D4C9A8;
  --border-light:    #E8E0C0;
  --text-primary:    var(--ink-brown);
  --text-secondary:  var(--ink-brown-light);
  --text-tertiary:   var(--ink-brown-lighter);
  --text-inverse:    var(--parchment-light);

  /* === 终端 — 磷光绿 CRT === */
  --terminal-bg:    #2A2622;
  --terminal-text:  #00FF41;
  --terminal-green: #00FF41;
  --terminal-border:#908880;

  /* === 侧边栏 === */
  --sidebar-bg:     #98ACD0;
  --sidebar-hover:  #7D9EAC;
  --sidebar-text:   #F0F4F3;
  --sidebar-active: #6A8A9A;

  /* === 核心宽度 === */
  --content-width: 850px;

  /* === 间距 === */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-37: 37px;

  /* === 圆角 === */
  --radius-sm:  4px;
  --radius:     6px;
  --radius-md:  8px;
  --radius-lg:  10px;
  --radius-full: 9999px;

  /* === 阴影 — 极简，仅用于微妙层次 === */
  --shadow-sm:   0 0 1px rgba(79,60,43,0.04);
  --shadow:      0 1px 2px rgba(79,60,43,0.04);
  --shadow-md:   0 1px 3px rgba(79,60,43,0.05);
  --shadow-lg:   0 2px 6px rgba(79,60,43,0.04);
  --shadow-xl:   0 2px 8px rgba(79,60,43,0.05);

  /* 叠纸效果 — 仅用描边 */
  --shadow-paper-stack: none;

  /* === 字体 === */
  --font-mono:     'Courier New', 'Courier', monospace;
  --font-terminal: 'Courier', 'Courier New', monospace;
  --font-serif:    'Georgia', 'Crimson Text', 'Times New Roman', serif;
  --font-sans:     -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;

  /* === 动画 === */
  --duration-fast:   150ms;
  --duration-normal: 250ms;
  --duration-slow:   400ms;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
}

#app {
  min-height: 100vh;
  font-family: var(--font-sans);
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: var(--font-sans);
  background-color: var(--bg-color);
  background-image:
    linear-gradient(rgba(79,60,43,0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(79,60,43,0.03) 1px, transparent 1px);
  background-size: 40px 40px;
  color: var(--text-primary);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* === 通用按钮 === */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: 8px 14px;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--duration-fast) ease;
  white-space: nowrap;
  font-family: var(--font-sans);
}

.btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--ink-brown);
  color: var(--text-inverse);
}

.btn-primary:hover:not(:disabled) {
  background: var(--ink-brown-dark);
}

.btn-secondary {
  background: var(--surface-color);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--surface-hover);
}

.btn-ghost {
  background: transparent;
  color: var(--text-secondary);
}

.btn-ghost:hover:not(:disabled) {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.btn-danger {
  background: var(--error-color);
  color: var(--text-inverse);
}

/* === 输入框 === */
.input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-family: inherit;
  background: var(--surface-color);
  color: var(--text-primary);
  transition: border-color var(--duration-fast) ease;
  outline: none;
}

.input:hover {
  border-color: #C4B898;
}

.input:focus {
  border-color: var(--slate-blue-dark);
}

.input::placeholder {
  color: var(--text-tertiary);
}

/* === 加载动画 === */
.loading-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--border-color);
  border-top-color: var(--ink-brown);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* === 滚动条 === */
::-webkit-scrollbar {
  width: 5px;
  height: 5px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #C4B898;
}

/* === 文本选择 === */
::selection {
  background: #CFE4EC;
  color: var(--ink-brown);
}
</style>
