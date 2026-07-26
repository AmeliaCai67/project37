import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import FilesView from '@/views/FilesView.vue'

const mockSetCurrentWorkspace = vi.fn()
const { mockGetList, mockSync } = vi.hoisted(() => ({
  mockGetList: vi.fn(() => Promise.resolve({ data: [] })),
  mockSync: vi.fn(() => Promise.resolve({ data: { new_files: 0 } }))
}))

const chatStore = {
  workspaces: [
    { id: 1, name: '上传空间', type: 'internal' },
    { id: 2, name: '期末数据', type: 'external' }
  ],
  currentWorkspaceId: 1,
  fetchWorkspaces: vi.fn(() => Promise.resolve()),
  setCurrentWorkspace: mockSetCurrentWorkspace,
  fetchRoadmap: vi.fn()
}

vi.mock('@/stores/chat.js', () => ({
  useChatStore: () => chatStore
}))

vi.mock('@/stores/user.js', () => ({
  useUserStore: () => ({
    canUpload: true,
    isAdmin: true
  })
}))

vi.mock('@/api/files.js', () => ({
  filesApi: {
    getList: mockGetList,
    upload: vi.fn(),
    delete: vi.fn()
  }
}))

vi.mock('@/api/workspaces.js', () => ({
  workspacesApi: { sync: mockSync }
}))

describe('FilesView workspace', () => {
  beforeEach(() => {
    chatStore.currentWorkspaceId = 1
    mockGetList.mockClear()
    mockSync.mockClear()
  })

  it('shows workspace selector when multiple workspaces exist', async () => {
    const wrapper = mount(FilesView)
    await flushPromises()
    expect(wrapper.find('select').exists()).toBe(true)
  })

  it('internal 空间不触发同步，加载完成后无文件才显示「档案柜为空」', async () => {
    const wrapper = mount(FilesView)
    await flushPromises()
    expect(mockSync).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('档案柜为空')
    expect(wrapper.text()).not.toContain('37 努力搬运中')
  })

  it('external 空间进入时先触发同步，同步期间显示「37 努力搬运中…」而非空档案柜', async () => {
    chatStore.currentWorkspaceId = 2
    let resolveList
    mockGetList.mockReturnValueOnce(new Promise(r => { resolveList = r }))

    const wrapper = mount(FilesView)
    await flushPromises()
    expect(mockSync).toHaveBeenCalledWith(2)

    // 列表未返回期间：显示搬运中，不显示「档案柜为空」
    expect(wrapper.text()).toContain('37 努力搬运中')
    expect(wrapper.text()).not.toContain('档案柜为空')

    resolveList({ data: [] })
    await flushPromises()
    expect(wrapper.text()).not.toContain('37 努力搬运中')
    expect(wrapper.text()).toContain('档案柜为空')
  })
})
