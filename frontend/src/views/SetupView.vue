<template>
  <div class="setup-page">
    <div class="setup-card">
      <h1>欢迎使用 Project 37</h1>
      <p class="subtitle">请输入 DeepSeek API Key，即可开始分析数据。</p>
      <form @submit.prevent="handleSubmit">
        <div class="field">
          <label>API Key</label>
          <input
            v-model="form.llm_api_key"
            type="password"
            class="input"
            placeholder="sk-..."
            required
          />
        </div>
        <div class="field">
          <label>模型</label>
          <select v-model="form.llm_model" class="input">
            <option value="deepseek-chat">deepseek-chat</option>
            <option value="deepseek-coder">deepseek-coder</option>
          </select>
        </div>
        <button type="submit" class="btn btn-primary" :disabled="saving">
          {{ saving ? '保存中...' : '开始使用' }}
        </button>
      </form>
      <p v-if="error" class="error">{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { configApi } from '@/api/config'

const router = useRouter()
const saving = ref(false)
const error = ref('')
const form = reactive({
  llm_api_key: '',
  llm_provider: 'deepseek',
  llm_model: 'deepseek-chat',
  llm_base_url: ''
})

async function handleSubmit() {
  saving.value = true
  error.value = ''
  try {
    await configApi.update(form)
    router.replace('/')
  } catch (e) {
    error.value = e.response?.data?.detail || '保存失败，请检查网络或 API Key'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.setup-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.setup-card {
  width: 100%;
  max-width: 420px;
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 32px;
}
h1 {
  font-size: 22px;
  margin-bottom: 8px;
}
.subtitle {
  color: var(--text-secondary);
  margin-bottom: 24px;
}
.field {
  margin-bottom: 16px;
}
label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}
.error {
  color: var(--error-color);
  margin-top: 12px;
  font-size: 13px;
}
</style>
