import { describe, it, expect, vi } from 'vitest'
import request from '@/api/request'
import { workspacesApi } from '@/api/workspaces'

vi.mock('@/api/request', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn()
  }
}))

describe('workspacesApi', () => {
  it('lists workspaces', async () => {
    request.get.mockResolvedValue({ data: [{ id: 1, name: '我的数据空间' }] })
    const res = await workspacesApi.list()
    expect(request.get).toHaveBeenCalledWith('/workspaces/list')
    expect(res.data[0].name).toBe('我的数据空间')
  })
})
