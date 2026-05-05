<template>
  <div class="login-page">
    <div class="login-content">
      <h1 class="login-title">Project <em>37</em></h1>
      <p class="login-subtitle">输入你的名字，开始问数</p>
      
      <div class="login-form">
        <input
          v-model="username"
          type="text"
          class="login-input"
          placeholder="你的名字"
          @keydown.enter.prevent="handleLogin"
          autofocus
        />
        <button
          class="login-btn"
          :disabled="loading || !username.trim()"
          @click="handleLogin"
        >
          <span v-if="loading" class="loading-spinner"></span>
          <span v-else>进入</span>
        </button>
      </div>
      
      <p v-if="error" class="login-error">{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const username = ref('')
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  const name = username.value.trim()
  if (!name) return
  
  loading.value = true
  error.value = ''
  
  const success = await userStore.login(name)
  loading.value = false
  
  if (success) {
    router.push('/')
  } else {
    error.value = '登录失败，请重试'
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-color);
  padding: 24px;
}

.login-content {
  width: 100%;
  max-width: 360px;
  text-align: center;
}

.login-title {
  font-family: var(--font-serif);
  font-size: 36px;
  font-weight: 700;
  font-style: italic;
  color: var(--ink-brown);
  margin-bottom: 8px;
  letter-spacing: -0.5px;
}

.login-subtitle {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 32px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.login-input {
  width: 100%;
  padding: 12px 16px;
  font-size: 15px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--parchment-light);
  color: var(--text-primary);
  outline: none;
  transition: border-color 0.15s ease;
  font-family: var(--font-sans);
}

.login-input:hover { border-color: #C4B898; }
.login-input:focus { border-color: var(--slate-blue-dark); }
.login-input::placeholder { color: var(--text-tertiary); }

.login-btn {
  width: 100%;
  padding: 12px 16px;
  font-size: 15px;
  font-weight: 500;
  color: var(--parchment-light);
  background: var(--ink-brown);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: opacity 0.15s ease;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-family: var(--font-sans);
}

.login-btn:hover:not(:disabled) { opacity: 0.85; }
.login-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.login-error {
  margin-top: 16px;
  font-size: 13px;
  color: var(--error-color);
}

.loading-spinner {
  width: 16px; height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>
