import request from './request'

export const configApi = {
  getStatus() {
    return request.get('/config/status')
  },
  update(data) {
    return request.post('/config', data)
  }
}
