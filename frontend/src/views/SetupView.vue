<template>
  <div class="setup-page">
    <div class="setup-card">
      <h1>欢迎使用 Project 37</h1>
      <p class="subtitle">请选择模型服务商并输入 API Key，即可开始分析数据。</p>
      <form @submit.prevent="handleSubmit">
        <div class="field">
          <label>服务商</label>
          <select v-model="form.llm_provider" class="input" @change="onProviderChange">
            <option value="deepseek">DeepSeek</option>
            <option value="kimi">Kimi（月之暗面）</option>
            <option value="qwen">通义千问 Qwen</option>
            <option value="zhipu">智谱 GLM</option>
            <option value="minimax">MiniMax</option>
            <option value="openai">OpenAI</option>
            <option value="custom">自定义（OpenAI 兼容）</option>
          </select>
        </div>
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
          <input v-model="form.llm_model" class="input" list="model-options" required />
          <datalist id="model-options">
            <option v-for="m in presetModels" :key="m" :value="m" />
          </datalist>
        </div>
        <div v-if="form.llm_provider === 'custom'" class="field">
          <label>Base URL</label>
          <input
            v-model="form.llm_base_url"
            class="input"
            placeholder="https://your-api-host/v1"
            required
          />
        </div>
        <div class="field">
          <label>备选模型（选填，主模型不可用时自动切换）</label>
          <select v-model="form.llm_fallback_provider" class="input" @change="onFallbackProviderChange">
            <option value="">不设置</option>
            <option value="deepseek">DeepSeek</option>
            <option value="kimi">Kimi（月之暗面）</option>
            <option value="qwen">通义千问 Qwen</option>
            <option value="zhipu">智谱 GLM</option>
            <option value="minimax">MiniMax</option>
            <option value="openai">OpenAI</option>
            <option value="custom">自定义（OpenAI 兼容）</option>
          </select>
        </div>
        <template v-if="form.llm_fallback_provider">
          <div class="field">
            <label>备选 API Key</label>
            <input
              v-model="form.llm_fallback_api_key"
              type="password"
              class="input"
              placeholder="sk-..."
              required
            />
          </div>
          <div class="field">
            <label>备选模型名称</label>
            <input v-model="form.llm_fallback_model" class="input" list="fallback-model-options" required />
            <datalist id="fallback-model-options">
              <option v-for="m in fallbackPresetModels" :key="m" :value="m" />
            </datalist>
          </div>
          <div v-if="form.llm_fallback_provider === 'custom'" class="field">
            <label>备选 Base URL</label>
            <input
              v-model="form.llm_fallback_base_url"
              class="input"
              placeholder="https://your-api-host/v1"
              required
            />
          </div>
        </template>
        <button type="submit" class="btn btn-primary" :disabled="saving">
          {{ saving ? '保存中...' : '开始使用' }}
        </button>
      </form>
      <p v-if="error" class="error">{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { configApi } from '@/api/config'

// OpenAI 兼容服务商预设（base_url 会随表单提交，自定义时必填）
const PRESETS = {
  deepseek: { base_url: 'https://api.deepseek.com/v1', models: ['deepseek-chat', 'deepseek-reasoner'] },
  kimi: { base_url: 'https://api.moonshot.cn/v1', models: ['kimi-k2-0905-preview', 'moonshot-v1-8k', 'moonshot-v1-32k'] },
  qwen: { base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', models: ['qwen-plus', 'qwen-max', 'qwen-turbo'] },
  zhipu: { base_url: 'https://open.bigmodel.cn/api/paas/v4', models: ['glm-4-plus', 'glm-4-flash'] },
  minimax: { base_url: 'https://api.minimax.chat/v1', models: ['MiniMax-Text-01', 'abab6.5s-chat'] },
  openai: { base_url: 'https://api.openai.com/v1', models: ['gpt-4o-mini', 'gpt-4o'] },
  custom: { base_url: '', models: [] },
}

const router = useRouter()
const saving = ref(false)
const error = ref('')
const form = reactive({
  llm_api_key: '',
  llm_provider: 'deepseek',
  llm_model: 'deepseek-chat',
  llm_base_url: 'https://api.deepseek.com/v1',
  llm_fallback_provider: '',
  llm_fallback_api_key: '',
  llm_fallback_model: '',
  llm_fallback_base_url: ''
})

const presetModels = computed(() => PRESETS[form.llm_provider]?.models || [])
const fallbackPresetModels = computed(() => PRESETS[form.llm_fallback_provider]?.models || [])

function onProviderChange() {
  const preset = PRESETS[form.llm_provider]
  form.llm_base_url = preset.base_url
  form.llm_model = preset.models[0] || ''
}

function onFallbackProviderChange() {
  const preset = PRESETS[form.llm_fallback_provider]
  if (!preset) {
    form.llm_fallback_api_key = ''
    form.llm_fallback_model = ''
    form.llm_fallback_base_url = ''
    return
  }
  form.llm_fallback_base_url = preset.base_url
  form.llm_fallback_model = preset.models[0] || ''
}

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
