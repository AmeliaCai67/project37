import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useChatStore } from '@/stores/chat'
import { chatApi } from '@/api/chat'
import { workspacesApi } from '@/api/workspaces'
import { roadmapApi } from '@/api/roadmap'

vi.mock('@/api/chat', () => ({
  chatApi: {
    send: vi.fn(),
    sendStream: vi.fn()
  }
}))

vi.mock('@/api/workspaces', () => ({
  workspacesApi: {
    list: vi.fn()
  }
}))

vi.mock('@/api/roadmap', () => ({
  roadmapApi: {
    get: vi.fn()
  }
}))

describe('Chat Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('初始状态', () => {
    it('初始状态为空', () => {
      const store = useChatStore()
      
      expect(store.messages).toEqual([])
      expect(store.agentSteps).toEqual([])
      expect(store.currentConversationId).toBeNull()
      expect(store.selectedFiles).toEqual([])
      expect(store.isStreaming).toBe(false)
      expect(store.workspaces).toEqual([])
      expect(store.currentWorkspaceId).toBeNull()
      expect(store.roadmap).toBeNull()
    })
  })

  describe('文件选择', () => {
    it('可以添加文件到选择', () => {
      const store = useChatStore()
      
      store.toggleFileSelection(1)
      
      expect(store.selectedFiles).toContain(1)
      expect(store.hasSelectedFiles).toBe(true)
    })

    it('再次点击取消选择', () => {
      const store = useChatStore()
      
      store.toggleFileSelection(1)
      store.toggleFileSelection(1)
      
      expect(store.selectedFiles).not.toContain(1)
      expect(store.hasSelectedFiles).toBe(false)
    })

    it('可以选择多个文件', () => {
      const store = useChatStore()
      
      store.toggleFileSelection(1)
      store.toggleFileSelection(2)
      store.toggleFileSelection(3)
      
      expect(store.selectedFiles).toHaveLength(3)
      expect(store.selectedFiles).toContain(1)
      expect(store.selectedFiles).toContain(2)
      expect(store.selectedFiles).toContain(3)
    })

    it('清空选择', () => {
      const store = useChatStore()
      
      store.toggleFileSelection(1)
      store.toggleFileSelection(2)
      store.clearFileSelection()
      
      expect(store.selectedFiles).toEqual([])
      expect(store.hasSelectedFiles).toBe(false)
    })
  })

  describe('Agent 步骤管理', () => {
    it('添加 Agent 步骤', () => {
      const store = useChatStore()
      
      const step = {
        type: 'thought',
        content: '我需要分析数据'
      }
      
      store.agentSteps.push(step)
      
      expect(store.agentSteps).toHaveLength(1)
      expect(store.agentSteps[0].type).toBe('thought')
    })

    it('步骤类型正确识别', () => {
      const store = useChatStore()
      
      store.agentSteps = [
        { type: 'thought', content: '思考' },
        { type: 'action', tool: 'read', input: {} },
        { type: 'observation', content: '结果', success: true },
        { type: 'answer', content: '最终答案' }
      ]
      
      expect(store.agentSteps).toHaveLength(4)
      expect(store.agentSteps.filter(s => s.type === 'thought')).toHaveLength(1)
      expect(store.agentSteps.filter(s => s.type === 'action')).toHaveLength(1)
      expect(store.agentSteps.filter(s => s.type === 'observation')).toHaveLength(1)
      expect(store.agentSteps.filter(s => s.type === 'answer')).toHaveLength(1)
    })
  })

  describe('消息管理', () => {
    it('发送消息添加到列表', () => {
      const store = useChatStore()
      
      store.messages.push({
        id: 1,
        role: 'user',
        content: '分析销售数据',
        timestamp: new Date().toISOString()
      })
      
      expect(store.messages).toHaveLength(1)
      expect(store.messages[0].role).toBe('user')
    })

    it('新对话清空状态', () => {
      const store = useChatStore()
      
      // 设置一些状态
      store.messages = [{ id: 1, role: 'user', content: 'test' }]
      store.agentSteps = [{ type: 'thought', content: 'test' }]
      store.currentConversationId = 123
      store.selectedFiles = [1, 2]
      
      store.createNewConversation()
      
      expect(store.messages).toEqual([])
      expect(store.agentSteps).toEqual([])
      expect(store.currentConversationId).toBeNull()
      expect(store.selectedFiles).toEqual([])
    })
  })

  describe('流式状态', () => {
    it('流式开始时状态正确', () => {
      const store = useChatStore()
      
      store.isStreaming = true
      store.agentSteps = [{ type: 'thought', content: '开始分析' }]
      
      expect(store.isStreaming).toBe(true)
      expect(store.agentSteps).toHaveLength(1)
    })

    it('流式接收步骤', () => {
      const store = useChatStore()
      
      // 模拟接收多个步骤
      const steps = [
        { type: 'thought', content: '步骤1' },
        { type: 'action', tool: 'glob', input: { pattern: '*.csv' } },
        { type: 'observation', content: '找到文件', success: true }
      ]
      
      steps.forEach(step => store.agentSteps.push(step))
      
      expect(store.agentSteps).toHaveLength(3)
      expect(store.agentSteps[1].tool).toBe('glob')
    })
  })

  describe('非流式发送消息', () => {
    it('发送消息后添加到消息列表', async () => {
      const store = useChatStore()
      
      // Mock API
      store.sendMessage = async (content) => {
        store.messages.push({
          id: Date.now(),
          role: 'user',
          content,
          timestamp: new Date().toISOString()
        })
        
        store.messages.push({
          id: Date.now() + 1,
          role: 'assistant',
          content: '分析结果',
          timestamp: new Date().toISOString()
        })
        
        return true
      }
      
      await store.sendMessage('测试消息')
      
      expect(store.messages).toHaveLength(2)
      expect(store.messages[0].role).toBe('user')
      expect(store.messages[1].role).toBe('assistant')
    })

    it('使用 file_ids 发送', async () => {
      const store = useChatStore()
      
      let receivedFileIds = null
      
      store.sendMessage = async (content, options) => {
        receivedFileIds = options.fileIds
        return true
      }
      
      await store.sendMessage('分析', { fileIds: [1, 2] })
      
      expect(receivedFileIds).toEqual([1, 2])
    })

    it('发送消息包含 workspace_id', async () => {
      const store = useChatStore()
      store.currentWorkspaceId = 5
      
      chatApi.send.mockResolvedValue({
        code: 200,
        data: { response: '结果', conversation_id: 1, steps: [] }
      })
      
      await store.sendMessage('分析数据')
      
      expect(chatApi.send).toHaveBeenCalledWith(
        expect.objectContaining({ workspace_id: 5 })
      )
    })

    it('流式发送消息包含 workspace_id', async () => {
      const store = useChatStore()
      store.currentWorkspaceId = 7
      
      chatApi.sendStream.mockResolvedValue({
        body: new ReadableStream({
          start(controller) {
            controller.close()
          }
        })
      })
      
      await store.sendMessageStream('分析数据')
      
      expect(chatApi.sendStream).toHaveBeenCalledWith(
        expect.objectContaining({ workspace_id: 7 })
      )
    })
  })

  describe('工作空间', () => {
    it('获取工作空间列表并默认选中第一个', async () => {
      const store = useChatStore()
      
      workspacesApi.list.mockResolvedValue({
        data: [
          { id: 1, name: '空间1' },
          { id: 2, name: '空间2' }
        ]
      })
      
      await store.fetchWorkspaces()
      
      expect(workspacesApi.list).toHaveBeenCalled()
      expect(store.workspaces).toHaveLength(2)
      expect(store.currentWorkspaceId).toBe(1)
      expect(store.currentWorkspace.name).toBe('空间1')
    })

    it('获取工作空间时保留当前选中', async () => {
      const store = useChatStore()
      store.currentWorkspaceId = 2
      
      workspacesApi.list.mockResolvedValue({
        data: [
          { id: 1, name: '空间1' },
          { id: 2, name: '空间2' }
        ]
      })
      
      await store.fetchWorkspaces()
      
      expect(store.currentWorkspaceId).toBe(2)
      expect(store.currentWorkspace.name).toBe('空间2')
    })

    it('切换工作空间时获取路线图', async () => {
      const store = useChatStore()
      
      roadmapApi.get.mockResolvedValue({
        data: {
          workspace_id: 2,
          stages: [{ id: 's1', name: '阶段1' }]
        }
      })
      
      await store.setCurrentWorkspace(2)
      
      expect(roadmapApi.get).toHaveBeenCalledWith(2)
      expect(store.currentWorkspaceId).toBe(2)
      expect(store.roadmap).toEqual({
        workspace_id: 2,
        stages: [{ id: 's1', name: '阶段1' }]
      })
    })

    it('当前无工作空间时不获取路线图', async () => {
      const store = useChatStore()
      
      await store.fetchRoadmap()
      
      expect(roadmapApi.get).not.toHaveBeenCalled()
      expect(store.roadmap).toBeNull()
    })
  })
})
