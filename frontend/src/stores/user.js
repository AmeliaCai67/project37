import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { authApi, getOrCreatePassword } from '@/api/auth'

export const useUserStore = defineStore('user', () => {
  // State
  const user = ref(null)
  const token = ref(localStorage.getItem('token') || '')
  const loading = ref(false)
  const loginError = ref('')
  // 用户主动退出后，本次会话内不再自动登录（避免退出后立即被 autoLogin 拉回）
  const skipAutoLogin = ref(false)
  let initPromise = null

  // Getters
  const isLoggedIn = computed(() => !!token.value && !!user.value)
  const userRole = computed(() => user.value?.role || 'user')
  const isReadonly = computed(() => userRole.value === 'user')
  const isAdmin = computed(() => userRole.value === 'admin')
  const canUpload = computed(() => isAdmin.value)
  const canDelete = computed(() => isAdmin.value)

  // Actions
  async function autoLogin() {
    loading.value = true
    try {
      const data = await authApi.autoLogin()
      if (data?.access_token) {
        token.value = data.access_token
        localStorage.setItem('token', data.access_token)
        await fetchUserInfo()
        return true
      }
      return false
    } catch (error) {
      console.error('Auto login error:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  async function login(username) {
    loading.value = true
    loginError.value = ''
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
        skipAutoLogin.value = false
        
        // 获取用户信息
        await fetchUserInfo()
        return true
      }
      return false
    } catch (error) {
      console.error('Login error:', error)
      // 把后端的具体原因（如「用户名或密码错误」、422 校验详情）透传给登录页
      const detail = error.response?.data?.detail
      if (typeof detail === 'string') {
        loginError.value = detail
      } else if (Array.isArray(detail) && detail.length) {
        loginError.value = detail[0]?.msg || '请求参数有误'
      } else {
        loginError.value = '登录失败，请检查网络后重试'
      }
      return false
    } finally {
      loading.value = false
    }
  }

  /**
   * 鉴权初始化：路由守卫必须 await 它再判断 isLoggedIn。
   * 有 token → 拉取用户信息；没有或失效 → personal 模式尝试 autoLogin（team 模式会 403，落到登录页）。
   * 幂等：多次调用复用同一个 Promise。
   */
  function initAuth() {
    if (!initPromise) {
      initPromise = (async () => {
        if (token.value) {
          await fetchUserInfo()
        }
        if (!user.value && !skipAutoLogin.value) {
          await autoLogin()
        }
        return isLoggedIn.value
      })()
    }
    return initPromise
  }

  function logout() {
    user.value = null
    token.value = ''
    localStorage.removeItem('token')
    skipAutoLogin.value = true
    initPromise = null
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
    loginError,
    isLoggedIn,
    userRole,
    isReadonly,
    isAdmin,
    canUpload,
    canDelete,
    login,
    logout,
    autoLogin,
    initAuth,
    fetchUserInfo
  }
})
