import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import SetupView from '@/views/SetupView.vue'
import { configApi } from '@/api/config'

const mockReplace = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ replace: mockReplace })
}))

vi.mock('@/api/config', () => ({
  configApi: { update: vi.fn(() => Promise.resolve()) }
}))

describe('SetupView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('默认选中 DeepSeek 并预填 base_url 与模型', () => {
    const wrapper = mount(SetupView)
    expect(wrapper.find('select').element.value).toBe('deepseek')
    expect(wrapper.vm.form.llm_base_url).toBe('https://api.deepseek.com/v1')
    expect(wrapper.vm.form.llm_model).toBe('deepseek-chat')
  })

  it('切换服务商自动填充 base_url 和默认模型', async () => {
    const wrapper = mount(SetupView)
    const select = wrapper.find('select')
    await select.setValue('kimi')
    expect(wrapper.vm.form.llm_base_url).toBe('https://api.moonshot.cn/v1')
    expect(wrapper.vm.form.llm_model).toBe('kimi-k2-0905-preview')

    await select.setValue('zhipu')
    expect(wrapper.vm.form.llm_base_url).toBe('https://open.bigmodel.cn/api/paas/v4')
    expect(wrapper.vm.form.llm_model).toBe('glm-4-plus')
  })

  it('选择自定义服务商时显示 Base URL 输入框', async () => {
    const wrapper = mount(SetupView)
    expect(wrapper.find('input[placeholder="https://your-api-host/v1"]').exists()).toBe(false)
    await wrapper.find('select').setValue('custom')
    expect(wrapper.find('input[placeholder="https://your-api-host/v1"]').exists()).toBe(true)
  })

  it('默认不设置备选模型，选中后显示备选字段并自动填充', async () => {
    const wrapper = mount(SetupView)
    expect(wrapper.vm.form.llm_fallback_provider).toBe('')
    expect(wrapper.find('input[list="fallback-model-options"]').exists()).toBe(false)

    const fallbackSelect = wrapper.findAll('select')[1]
    await fallbackSelect.setValue('qwen')
    expect(wrapper.vm.form.llm_fallback_base_url).toBe('https://dashscope.aliyuncs.com/compatible-mode/v1')
    expect(wrapper.vm.form.llm_fallback_model).toBe('qwen-plus')
    expect(wrapper.find('input[list="fallback-model-options"]').exists()).toBe(true)
  })

  it('取消备选后清空备选字段', async () => {
    const wrapper = mount(SetupView)
    const fallbackSelect = wrapper.findAll('select')[1]
    await fallbackSelect.setValue('kimi')
    await fallbackSelect.setValue('')
    expect(wrapper.vm.form.llm_fallback_model).toBe('')
    expect(wrapper.vm.form.llm_fallback_base_url).toBe('')
  })

  it('提交时携带所选服务商配置', async () => {
    const wrapper = mount(SetupView)
    await wrapper.find('select').setValue('qwen')
    await wrapper.find('input[type="password"]').setValue('sk-test')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(configApi.update).toHaveBeenCalledWith(expect.objectContaining({
      llm_provider: 'qwen',
      llm_api_key: 'sk-test',
      llm_base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
      llm_model: 'qwen-plus'
    }))
    expect(mockReplace).toHaveBeenCalledWith('/')
  })

  it('提交时携带备选模型配置', async () => {
    const wrapper = mount(SetupView)
    await wrapper.find('input[type="password"]').setValue('sk-main')
    const fallbackSelect = wrapper.findAll('select')[1]
    await fallbackSelect.setValue('kimi')
    await wrapper.findAll('input[type="password"]')[1].setValue('sk-fb')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(configApi.update).toHaveBeenCalledWith(expect.objectContaining({
      llm_fallback_provider: 'kimi',
      llm_fallback_api_key: 'sk-fb',
      llm_fallback_model: 'kimi-k2-0905-preview',
      llm_fallback_base_url: 'https://api.moonshot.cn/v1'
    }))
  })
})
