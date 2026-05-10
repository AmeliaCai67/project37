import request from './request'

/**
 * 获取或生成用户的强随机密码
 *
 * 每个用户名对应一个独立的密码，通过 crypto.randomUUID() 生成（底层调用
 * crypto.getRandomValues，密码学强度足够）。密码存储在浏览器 localStorage 中，
 * 首次登录时自动生成，后续从 localStorage 读取。
 *
 * 注意：如果用户清除浏览器数据（localStorage），密码将丢失，需要重新注册。
 */
export function getOrCreatePassword(username) {
  const key = `p37_pwd_${username}`
  let pwd = localStorage.getItem(key)
  if (!pwd) {
    pwd = crypto.randomUUID() + crypto.randomUUID()
    localStorage.setItem(key, pwd)
  }
  return pwd
}

export const authApi = {
  login(data) {
    // 登录使用 form-data 格式（OAuth2PasswordRequestForm）
    const params = new URLSearchParams()
    params.append('username', data.username)
    params.append('password', data.password)
    
    return request.post('/auth/login', params, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    })
  },

  // JSON 格式登录
  loginJson(data) {
    return request.post('/auth/login/json', {
      username: data.username,
      password: data.password
    })
  },

  register(data) {
    const password = data.password || getOrCreatePassword(data.username)
    return request.post('/auth/register', {
      username: data.username,
      email: data.email || `${data.username}@example.com`,
      password: password
    })
  },

  getMe() {
    return request.get('/auth/me')
  }
}
