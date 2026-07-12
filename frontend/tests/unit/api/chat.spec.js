import { describe, it, expect, vi, beforeEach } from 'vitest'
import { chatApi } from '@/api/chat'

describe('Chat API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  describe('非流式发送', () => {
    it('发送消息包含正确参数', async () => {
      const mockResponse = {
        data: {
          success: true,
          data: {
            response: '分析结果',
            conversation_id: 123,
            steps: []
          }
        }
      }
      
      // Mock request
      chatApi.send = vi.fn().mockResolvedValue(mockResponse)
      
      const result = await chatApi.send({
        message: '分析数据',
        conversation_id: null,
        file_ids: [1, 2]
      })
      
      expect(chatApi.send).toHaveBeenCalledWith({
        message: '分析数据',
        conversation_id: null,
        file_ids: [1, 2]
      })
      expect(result.data.success).toBe(true)
    })

    it('包含对话 ID 时继续对话', async () => {
      chatApi.send = vi.fn().mockResolvedValue({
        data: { success: true, data: { conversation_id: 123 } }
      })
      
      await chatApi.send({
        message: '继续问',
        conversation_id: 123
      })
      
      expect(chatApi.send).toHaveBeenCalledWith(
        expect.objectContaining({ conversation_id: 123 })
      )
    })
  })

  describe('流式发送', () => {
    it('使用 fetch 发送请求', async () => {
      localStorage.setItem('token', 'test_token')
      
      const mockResponse = {
        body: new ReadableStream({
          start(controller) {
            controller.close()
          }
        })
      }
      
      global.fetch = vi.fn().mockResolvedValue(mockResponse)
      
      await chatApi.sendStream({
        message: '流式测试',
        file_ids: []
      })
      
      expect(fetch).toHaveBeenCalledWith(
        '/api/chat/send/stream',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Authorization': 'Bearer test_token'
          })
        })
      )
    })

    it('包含正确的请求体', async () => {
      localStorage.setItem('token', 'test_token')
      
      global.fetch = vi.fn().mockResolvedValue({
        body: new ReadableStream({ start(c) { c.close() } })
      })
      
      await chatApi.sendStream({
        message: '测试',
        conversation_id: 456,
        file_ids: [1]
      })
      
      const callArgs = fetch.mock.calls[0][1]
      const body = JSON.parse(callArgs.body)
      
      expect(body.message).toBe('测试')
      expect(body.conversation_id).toBe(456)
      expect(body.file_ids).toEqual([1])
    })

    it('没有 token 时发送空字符串', async () => {
      localStorage.clear()
      
      global.fetch = vi.fn().mockResolvedValue({
        body: new ReadableStream({ start(c) { c.close() } })
      })
      
      await chatApi.sendStream({ message: 'test' })
      
      const callArgs = fetch.mock.calls[0][1]
      expect(callArgs.headers.Authorization).toBe('Bearer ')
    })
  })

  describe('获取对话列表', () => {
    it('获取列表', async () => {
      const mockResponse = {
        data: {
          items: [
            { id: 1, title: '对话1' },
            { id: 2, title: '对话2' }
          ]
        }
      }
      
      chatApi.getConversations = vi.fn().mockResolvedValue(mockResponse)
      
      const result = await chatApi.getConversations()
      
      expect(result.data.items).toHaveLength(2)
    })

    it('支持分页参数', async () => {
      chatApi.getConversations = vi.fn().mockResolvedValue({ data: { items: [] } })
      
      await chatApi.getConversations({ skip: 10, limit: 20 })
      
      expect(chatApi.getConversations).toHaveBeenCalledWith(
        expect.objectContaining({ skip: 10, limit: 20 })
      )
    })
  })

  describe('获取对话详情', () => {
    it('获取指定对话', async () => {
      const mockResponse = {
        data: {
          id: 1,
          messages: [],
          steps: []
        }
      }
      
      chatApi.getConversation = vi.fn().mockResolvedValue(mockResponse)
      
      const result = await chatApi.getConversation(123)
      
      expect(chatApi.getConversation).toHaveBeenCalledWith(123)
      expect(result.data.id).toBe(1)
    })
  })

  describe('删除对话', () => {
    it('删除指定对话', async () => {
      chatApi.deleteConversation = vi.fn().mockResolvedValue({ data: { success: true } })
      
      await chatApi.deleteConversation(123)
      
      expect(chatApi.deleteConversation).toHaveBeenCalledWith(123)
    })
  })
})
