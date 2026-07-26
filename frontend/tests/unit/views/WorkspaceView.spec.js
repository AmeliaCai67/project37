import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import WorkspaceView from '@/views/WorkspaceView.vue'
import { systemApi } from '@/api/system'
import { workspacesApi } from '@/api/workspaces'

const mockPush = vi.fn()
const mockFetchWorkspaces = vi.fn(() => Promise.resolve())
const mockSetCurrentWorkspace = vi.fn(() => Promise.resolve())

const store = {
  workspaces: [
    { id: 1, name: '我的数据空间', type: 'internal', output_path: '/out/1' },
    { id: 2, name: '期末数据', type: 'external', source_path: '/Users/t/data', output_path: '/out/2' }
  ],
  currentWorkspaceId: 1,
  roadmap: { questions: [{ question: 'Q1' }] },
  pendingRoadmapModal: false,
  fetchWorkspaces: mockFetchWorkspaces,
  setCurrentWorkspace: mockSetCurrentWorkspace
}

vi.mock('@/stores/chat.js', () => ({
  useChatStore: () => store
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush })
}))

vi.mock('@/api/system', () => ({
  systemApi: { pickDirectory: vi.fn() }
}))

vi.mock('@/api/workspaces', () => ({
  workspacesApi: {
    mount: vi.fn(),
    unmount: vi.fn(() => Promise.resolve()),
    updateOutputPath: vi.fn(() => Promise.resolve())
  }
}))

describe('WorkspaceView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    store.pendingRoadmapModal = false
  })

  it('渲染已挂载空间列表，当前空间高亮', async () => {
    const wrapper = mount(WorkspaceView)
    await flushPromises()
    const cards = wrapper.findAll('.workspace-card')
    expect(cards).toHaveLength(2)
    expect(cards[0].classes()).toContain('current')
    expect(mockFetchWorkspaces).toHaveBeenCalled()
  })

  it('pick-directory 成功：回填路径与默认空间名', async () => {
    systemApi.pickDirectory.mockResolvedValue({ path: '/Users/t/20260718_225124_销售数据' })
    const wrapper = mount(WorkspaceView)
    await flushPromises()

    await wrapper.find('.upload-btn').trigger('click')
    await flushPromises()

    expect(wrapper.find('.path-input').element.value).toBe('/Users/t/20260718_225124_销售数据')
    expect(wrapper.find('.name-input').element.value).toBe('销售数据')
  })

  it('pick-directory 用户取消：显示提示', async () => {
    systemApi.pickDirectory.mockResolvedValue({ path: null })
    const wrapper = mount(WorkspaceView)
    await flushPromises()

    await wrapper.find('.upload-btn').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('未选择文件夹')
  })

  it('pick-directory 503：提示环境不支持，回退手动输入', async () => {
    systemApi.pickDirectory.mockRejectedValue({ response: { status: 503 } })
    const wrapper = mount(WorkspaceView)
    await flushPromises()

    await wrapper.find('.upload-btn').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('不支持系统目录选择器')
  })

  it('挂载成功：调 mount API、切换空间、设置待显示弹窗并跳回对话页', async () => {
    workspacesApi.mount.mockResolvedValue({ data: { id: 3 } })
    const wrapper = mount(WorkspaceView)
    await flushPromises()

    await wrapper.find('.path-input').setValue('/Users/t/newdata')
    await wrapper.find('.name-input').setValue('新数据')
    await wrapper.find('.mount-submit').trigger('click')
    await flushPromises()

    expect(workspacesApi.mount).toHaveBeenCalledWith({ local_path: '/Users/t/newdata', name: '新数据' })
    expect(mockSetCurrentWorkspace).toHaveBeenCalledWith(3)
    expect(store.pendingRoadmapModal).toBe(true)
    expect(mockPush).toHaveBeenCalledWith('/')
  })

  it('重复路径：不重复挂载，直接切换并跳回', async () => {
    const wrapper = mount(WorkspaceView)
    await flushPromises()

    await wrapper.find('.path-input').setValue('/Users/t/data')
    await wrapper.find('.mount-submit').trigger('click')
    await flushPromises()

    expect(workspacesApi.mount).not.toHaveBeenCalled()
    expect(mockSetCurrentWorkspace).toHaveBeenCalledWith(2)
    expect(mockPush).toHaveBeenCalledWith('/')
  })

  it('输出路径内联编辑保存', async () => {
    const wrapper = mount(WorkspaceView)
    await flushPromises()

    const editBtns = wrapper.findAll('.edit-output-btn')
    await editBtns[0].trigger('click')
    await wrapper.find('.output-edit-input').setValue('/new/out')
    const saveBtn = wrapper.findAll('.output-btn').find(b => b.text() === '保存')
    await saveBtn.trigger('click')
    await flushPromises()

    expect(workspacesApi.updateOutputPath).toHaveBeenCalledWith(1, '/new/out')
  })
})
