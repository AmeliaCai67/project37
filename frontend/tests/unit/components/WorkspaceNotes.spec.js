import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import WorkspaceNotes from '@/components/WorkspaceNotes.vue'

const mockSetCurrentWorkspace = vi.fn(() => Promise.resolve())
const mockPush = vi.fn()

const store = {
  workspaces: [
    { id: 1, name: '我的数据空间', type: 'internal', output_path: '/out/1' },
    { id: 2, name: '20260718_225124_期末数据', type: 'external', output_path: '/out/2' }
  ],
  currentWorkspaceId: 2,
  currentWorkspace: { id: 2, name: '20260718_225124_期末数据', type: 'external', output_path: '/out/2' },
  setCurrentWorkspace: mockSetCurrentWorkspace
}

vi.mock('@/stores/chat.js', () => ({
  useChatStore: () => store
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush })
}))

describe('WorkspaceNotes', () => {
  it('展示当前空间名（去时间戳前缀）与输出路径', () => {
    const wrapper = mount(WorkspaceNotes)
    expect(wrapper.text()).toContain('期末数据')
    expect(wrapper.text()).not.toContain('20260718_225124')
    expect(wrapper.text()).toContain('/out/2')
  })

  it('点击切换空间展开列表并切换', async () => {
    const wrapper = mount(WorkspaceNotes)
    expect(wrapper.find('.switch-list').exists()).toBe(false)
    await wrapper.find('.note-head').trigger('click')
    expect(wrapper.find('.switch-list').exists()).toBe(true)

    const items = wrapper.findAll('.switch-item')
    expect(items).toHaveLength(2)
    await items[0].trigger('click')
    await flushPromises()
    expect(mockSetCurrentWorkspace).toHaveBeenCalledWith(1)
  })

  it('输出路径便利贴点击跳转 /workspace', async () => {
    const wrapper = mount(WorkspaceNotes)
    await wrapper.find('.note-output').trigger('click')
    expect(mockPush).toHaveBeenCalledWith('/workspace')
  })
})
