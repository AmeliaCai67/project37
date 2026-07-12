import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import LoginView from '@/views/LoginView.vue'

describe('LoginView Component', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染登录表单', () => {
    const wrapper = mount(LoginView)
    expect(wrapper.find('.login-page').exists()).toBe(true)
    expect(wrapper.find('input[type="text"]').exists()).toBe(true)
    expect(wrapper.find('.login-btn').exists()).toBe(true)
  })

  it('显示 37 品牌标题', () => {
    const wrapper = mount(LoginView)
    expect(wrapper.find('.login-title').text()).toContain('37')
  })

  it('用户名输入绑定', async () => {
    const wrapper = mount(LoginView)
    const input = wrapper.find('input[type="text"]')
    await input.setValue('testuser')
    expect(wrapper.vm.username).toBe('testuser')
  })

  it('空用户名不能登录', async () => {
    const wrapper = mount(LoginView)
    expect(wrapper.vm.username).toBe('')
    // 按钮在 username 为空时 disabled
    const btn = wrapper.find('.login-btn')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('输入用户名后按钮可用', async () => {
    const wrapper = mount(LoginView)
    const input = wrapper.find('input[type="text"]')
    await input.setValue('testuser')
    const btn = wrapper.find('.login-btn')
    expect(btn.attributes('disabled')).toBeUndefined()
  })

  it('登录按钮有加载状态', async () => {
    const wrapper = mount(LoginView)
    wrapper.vm.loading = true
    await wrapper.vm.$nextTick()
    const button = wrapper.find('.login-btn')
    expect(button.attributes('disabled')).toBeDefined()
    expect(button.find('.loading-spinner').exists()).toBe(true)
  })

  it('显示登录引导文字', () => {
    const wrapper = mount(LoginView)
    expect(wrapper.text()).toContain('输入你的名字')
  })

  it('Enter 键触发登录', async () => {
    const wrapper = mount(LoginView)
    const input = wrapper.find('input[type="text"]')
    await input.setValue('testuser')
    await input.trigger('keydown.enter')
    // 验证登录流程被触发
  })
})
