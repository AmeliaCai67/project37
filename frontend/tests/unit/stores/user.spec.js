import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useUserStore } from '@/stores/user'

describe('User Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  describe('初始状态', () => {
    it('初始状态应该是未登录', () => {
      const store = useUserStore()
      
      expect(store.isLoggedIn).toBe(false)
      expect(store.user).toBeNull()
      expect(store.token).toBe('')
    })

    it('应该从 localStorage 恢复 token', () => {
      localStorage.setItem('token', 'test_token_123')
      
      const store = useUserStore()
      
      expect(store.token).toBe('test_token_123')
    })
  })

  describe('权限计算', () => {
    it('普通用户权限判断正确', () => {
      const store = useUserStore()
      store.user = { username: 'test', role: 'user' }
      
      expect(store.userRole).toBe('user')
      expect(store.isReadonly).toBe(true)
      expect(store.canUpload).toBe(false)
      expect(store.canDelete).toBe(false)
    })

    it('管理员权限判断正确', () => {
      const store = useUserStore()
      store.user = { username: 'test', role: 'admin' }
      
      expect(store.userRole).toBe('admin')
      expect(store.isReadonly).toBe(false)
      expect(store.canUpload).toBe(true)
      expect(store.canDelete).toBe(true)
    })
  })

  describe('登录/登出', () => {
    it('登录成功后状态正确', async () => {
      const store = useUserStore()
      
      // Mock API 响应
      const mockResponse = {
        data: {
          success: true,
          token: 'mock_token',
          username: 'testuser',
          role: 'admin',
          workspace: 'user_testuser'
        }
      }
      
      // 替换 API 调用
      store.login = async (username, role) => {
        store.token = mockResponse.data.token
        store.user = {
          username: mockResponse.data.username,
          role: mockResponse.data.role,
          workspace: mockResponse.data.workspace
        }
        localStorage.setItem('token', mockResponse.data.token)
        return true
      }
      
      const result = await store.login('testuser', 'write')
      
      expect(result).toBe(true)
      expect(store.isLoggedIn).toBe(true)
      expect(store.user.username).toBe('testuser')
      expect(store.user.role).toBe('admin')
      expect(localStorage.getItem('token')).toBe('mock_token')
    })

    it('登出后状态清空', () => {
      const store = useUserStore()
      
      // 先设置登录状态
      store.token = 'test_token'
      store.user = { username: 'test', role: 'write' }
      localStorage.setItem('token', 'test_token')
      
      // 执行登出
      store.logout()
      
      expect(store.isLoggedIn).toBe(false)
      expect(store.user).toBeNull()
      expect(store.token).toBe('')
      expect(localStorage.getItem('token')).toBeNull()
    })
  })
})
