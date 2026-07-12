import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import FilesView from '@/views/FilesView.vue'

const mockSetCurrentWorkspace = vi.fn()

vi.mock('@/stores/chat.js', () => ({
  useChatStore: () => ({
    workspaces: [
      { id: 1, name: '上传空间' },
      { id: 2, name: '期末数据' }
    ],
    currentWorkspaceId: 1,
    fetchWorkspaces: vi.fn(() => Promise.resolve()),
    setCurrentWorkspace: mockSetCurrentWorkspace,
    fetchRoadmap: vi.fn()
  })
}))

vi.mock('@/stores/user.js', () => ({
  useUserStore: () => ({
    canUpload: true,
    isAdmin: true
  })
}))

vi.mock('@/api/files.js', () => ({
  filesApi: {
    getList: vi.fn(() => Promise.resolve({ data: [] })),
    upload: vi.fn(),
    delete: vi.fn()
  }
}))

describe('FilesView workspace', () => {
  it('shows workspace selector when multiple workspaces exist', async () => {
    const wrapper = mount(FilesView)
    await flushPromises()
    expect(wrapper.find('select').exists()).toBe(true)
  })
})
