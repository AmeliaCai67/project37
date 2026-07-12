import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, config } from '@vue/test-utils'
import { setActivePinia } from 'pinia'
import { useChatStore } from '@/stores/chat'
import WorkspaceBar from '@/components/WorkspaceBar.vue'

const globalPinia = config.global.plugins[0]

vi.mock('@/api/workspaces', () => ({
  workspacesApi: {
    list: vi.fn().mockResolvedValue({ data: [] }),
    updateOutputPath: vi.fn().mockResolvedValue({ code: 200 })
  }
}))

vi.mock('@/api/roadmap', () => ({
  roadmapApi: {
    get: vi.fn().mockResolvedValue({ data: null })
  }
}))

function setupStore(workspace) {
  setActivePinia(globalPinia)
  const store = useChatStore()
  store.workspaces = workspace ? [workspace] : []
  store.currentWorkspaceId = workspace ? workspace.id : null
  return store
}

describe('WorkspaceBar', () => {
  beforeEach(() => {
    window.prompt = vi.fn()
    setupStore(null)
  })

  it('renders current workspace name and output path', () => {
    setupStore({ id: 1, name: '期末数据', type: 'external', output_path: '/tmp/out' })

    const wrapper = mount(WorkspaceBar)
    expect(wrapper.text()).toContain('期末数据')
    expect(wrapper.text()).toContain('/tmp/out')
  })

  it('displays type label for internal and external workspaces', async () => {
    const store = setupStore({ id: 1, name: '内部空间', type: 'internal', output_path: '/tmp/internal' })

    const wrapper = mount(WorkspaceBar)
    expect(wrapper.text()).toContain('上传空间')

    store.workspaces = [
      { id: 1, name: '内部空间', type: 'internal', output_path: '/tmp/internal' },
      { id: 2, name: '本地挂载', type: 'external', output_path: '/tmp/external' }
    ]
    store.currentWorkspaceId = 2
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('本地挂载')
  })

  it('switches workspace when selecting a different option', async () => {
    const store = setupStore({ id: 1, name: '空间 A', type: 'internal', output_path: '/tmp/a' })
    store.workspaces = [
      { id: 1, name: '空间 A', type: 'internal', output_path: '/tmp/a' },
      { id: 2, name: '空间 B', type: 'external', output_path: '/tmp/b' }
    ]

    const wrapper = mount(WorkspaceBar)
    const select = wrapper.find('select')
    await select.setValue('2')

    expect(store.currentWorkspaceId).toBe(2)
  })

  it('emits mount event when mount button is clicked', async () => {
    setupStore({ id: 1, name: '期末数据', type: 'external', output_path: '/tmp/out' })

    const wrapper = mount(WorkspaceBar)
    const button = wrapper.find('button.mount-btn')
    await button.trigger('click')

    expect(wrapper.emitted('mount')).toHaveLength(1)
  })

  it('updates output path via prompt and refreshes workspace list', async () => {
    const { workspacesApi } = await import('@/api/workspaces')
    window.prompt.mockReturnValue('/new/output')

    setupStore({ id: 1, name: '期末数据', type: 'external', output_path: '/tmp/out' })

    const wrapper = mount(WorkspaceBar)
    const button = wrapper.find('button.edit-output-btn')
    await button.trigger('click')
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(window.prompt).toHaveBeenCalledWith('修改输出目录：', '/tmp/out')
    expect(workspacesApi.updateOutputPath).toHaveBeenCalledWith(1, '/new/output')
    expect(workspacesApi.list).toHaveBeenCalled()
  })
})
