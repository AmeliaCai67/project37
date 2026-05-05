import request from './request'

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
    const password = data.password || (data.username.length >= 6 ? data.username : data.username + '123456')
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
