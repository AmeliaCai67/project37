import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { authApi, getOrCreatePassword } from '@/api/auth'

export const useUserStore = defineStore('user', () => {
  // State
  const user = ref(null)
  const token = ref(localStorage.getItem('token') || '')
  const loading = ref(false)

  // Getters
  const isLoggedIn = computed(() => !!token.value && !!user.value)
  const userRole = computed(() => user.value?.role || 'user')
  const isReadonly = computed(() => userRole.value === 'user')
  const isAdmin = computed(() => userRole.value === 'admin')
  const canUpload = computed(() => isAdmin.value)
  const canDelete = computed(() => isAdmin.value)

  // Actions
  async function login(username) {
    loading.value = true
    try {
      const password = getOrCreatePassword(username)
      
      // 先尝试直接登录
      let data
      try {
        data = await authApi.login({ username, password })
      } catch (error) {
        // 登录失败，可能是用户不存在，尝试注册
        if (error.response?.status === 401) {
          try {
            await authApi.register({ username, password })
            // 注册成功，再次登录
            data = await authApi.login({ username, password })
          } catch (registerError) {
            console.error('Register error:', registerError)
            // 注册失败，可能是用户已存在但密码不对
            throw registerError
          }
        } else {
          throw error
        }
      }
      
      if (data?.access_token) {
        token.value = data.access_token
        localStorage.setItem('token', token.value)
        
        // 获取用户信息
        await fetchUserInfo()
        return true
      }
      return false
    } catch (error) {
      console.error('Login error:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  function logout() {
    user.value = null
    token.value = ''
    localStorage.removeItem('token')
  }

  async function fetchUserInfo() {
    if (!token.value) return
    try {
      const data = await authApi.getMe()
      user.value = data
    } catch {
      logout()
    }
  }

  return {
    user,
    token,
    loading,
    isLoggedIn,
    userRole,
    isReadonly,
    isAdmin,
    canUpload,
    canDelete,
    login,
    logout,
    fetchUserInfo
  }
})
