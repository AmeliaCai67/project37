import request from './request'

export const chatApi = {
  /**
   * 发送消息（非流式）
   */
  send(data) {
    return request.post('/chat/send', data)
  },

  /**
   * 发送消息（流式）
   * 返回原生 Response 对象用于读取 SSE
   */
  sendStream(data) {
    return fetch('/api/chat/send/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
      },
      body: JSON.stringify(data)
    })
  },

  /**
   * 获取对话列表
   */
  getConversations(params = {}) {
    return request.get('/conversations/list', { params })
  },

  /**
   * 获取对话详情（包含 Agent 步骤）
   */
  getConversation(id) {
    return request.get(`/conversations/${id}`)
  },

  /**
   * 删除对话
   */
  deleteConversation(id) {
    return request.delete(`/conversations/${id}`)
  }
}
