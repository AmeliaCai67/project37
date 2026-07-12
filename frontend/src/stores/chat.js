import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { chatApi } from '@/api/chat'
import { workspacesApi } from '@/api/workspaces'
import { roadmapApi } from '@/api/roadmap'

/**
 * Agent 步骤类型
 * - thought: AI 思考
 * - action: 执行工具
 * - observation: 工具返回
 * - answer: 最终答案
 * - error: 错误
 * - system: 系统消息
 */

export const useChatStore = defineStore('chat', () => {
  // State
  const conversations = ref([])
  const currentConversationId = ref(null)
  const messages = ref([])
  const agentSteps = ref([])  // ReAct 步骤
  const isStreaming = ref(false)
  const selectedFiles = ref([])  // 只读用户选择的文件

  // Workspace state
  const workspaces = ref([])
  const currentWorkspaceId = ref(null)
  const roadmap = ref(null)

  // Getters
  const currentConversation = computed(() => {
    return conversations.value.find(c => c.id === currentConversationId.value)
  })

  const currentWorkspace = computed(() =>
    workspaces.value.find(w => w.id === currentWorkspaceId.value)
  )

  const hasSelectedFiles = computed(() => selectedFiles.value.length > 0)

  // Actions
  
  /**
   * 发送消息（非流式）
   */
  async function sendMessage(content, options = {}) {
    const message = {
      id: Date.now(),
      role: 'user',
      content,
      timestamp: new Date().toISOString()
    }
    messages.value.push(message)

    try {
      const res = await chatApi.send({
        message: content,
        conversation_id: currentConversationId.value,
        file_ids: options.fileIds || selectedFiles.value,
        workspace_id: currentWorkspaceId.value
      })

      if (res.code === 200) {
        const { response, conversation_id, steps } = res.data
        
        // 保存 Agent 步骤
        if (steps) {
          agentSteps.value = steps
        }

        // 添加 AI 回复
        messages.value.push({
          id: Date.now() + 1,
          role: 'assistant',
          content: response,
          timestamp: new Date().toISOString()
        })

        // 更新对话 ID
        if (!currentConversationId.value) {
          currentConversationId.value = conversation_id
          conversations.value.unshift({
            id: conversation_id,
            title: content.slice(0, 20) + (content.length > 20 ? '...' : '')
          })
        }

        return true
      }
    } catch (error) {
      messages.value.push({
        id: Date.now() + 1,
        role: 'system',
        content: `错误: ${error.message}`,
        timestamp: new Date().toISOString()
      })
      return false
    }
  }

  /**
   * 发送消息（流式）
   * 实时接收 Agent 思考过程
   */
  async function sendMessageStream(content, options = {}, onStep) {
    const message = {
      id: Date.now(),
      role: 'user',
      content,
      timestamp: new Date().toISOString()
    }
    messages.value.push(message)

    isStreaming.value = true
    agentSteps.value = []

    try {
      const response = await chatApi.sendStream({
        message: content,
        conversation_id: currentConversationId.value,
        file_ids: options.fileIds || selectedFiles.value,
        workspace_id: currentWorkspaceId.value
      })

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let aiMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
        steps: []
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value)
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            
            if (data === '[DONE]') {
              messages.value.push(aiMessage)
              isStreaming.value = false
              return true
            }

            try {
              const event = JSON.parse(data)

              // 接收 conversation_id（新对话时后端通过 SSE 发送）
              if (event.type === 'conversation_id') {
                if (!currentConversationId.value) {
                  currentConversationId.value = event.conversation_id
                  conversations.value.unshift({
                    id: event.conversation_id,
                    title: content.slice(0, 20) + (content.length > 20 ? '...' : '')
                  })
                }
                continue
              }

              // 记录 Agent 步骤
              if (['thought', 'action', 'observation'].includes(event.type)) {
                agentSteps.value.push(event)
                aiMessage.steps.push(event)
                if (onStep) onStep(event)
              }
              
              // 累积最终答案
              if (event.type === 'answer') {
                aiMessage.content = event.content
              }

              // 记录结果保存路径
              if (event.type === 'metadata' && event.saved_path) {
                aiMessage.savedPath = event.saved_path
              }

              if (event.type === 'error') {
                aiMessage.content = `错误: ${event.content}`
              }
            } catch {
              // 非 JSON 数据，累积到答案
              aiMessage.content += data
            }
          }
        }
      }

      return true
    } catch (error) {
      messages.value.push({
        id: Date.now() + 1,
        role: 'system',
        content: `错误: ${error.message}`,
        timestamp: new Date().toISOString()
      })
      return false
    } finally {
      isStreaming.value = false
    }
  }

  /**
   * 选择文件（只读用户）
   */
  function toggleFileSelection(fileId) {
    const index = selectedFiles.value.indexOf(fileId)
    if (index > -1) {
      selectedFiles.value.splice(index, 1)
    } else {
      selectedFiles.value.push(fileId)
    }
  }

  /**
   * 清空选择
   */
  function clearFileSelection() {
    selectedFiles.value = []
  }

  /**
   * 创建新对话
   */
  function createNewConversation() {
    currentConversationId.value = null
    messages.value = []
    agentSteps.value = []
    selectedFiles.value = []
  }

  /**
   * 获取对话列表
   */
  async function fetchConversations() {
    try {
      const res = await chatApi.getConversations()
      conversations.value = res.data || []
    } catch (error) {
      console.error('获取对话列表失败:', error)
    }
  }

  /**
   * 获取工作空间列表
   */
  async function fetchWorkspaces() {
    try {
      const res = await workspacesApi.list()
      workspaces.value = res.data || []
      if (!currentWorkspaceId.value && workspaces.value.length > 0) {
        currentWorkspaceId.value = workspaces.value[0].id
      }
    } catch (error) {
      console.error('获取工作空间列表失败:', error)
    }
  }

  /**
   * 获取路线图
   */
  async function fetchRoadmap() {
    if (!currentWorkspaceId.value) return
    const res = await roadmapApi.get(currentWorkspaceId.value)
    roadmap.value = res.data
  }

  /**
   * 设置当前工作空间
   */
  async function setCurrentWorkspace(id) {
    currentWorkspaceId.value = id
    await fetchRoadmap()
  }

  /**
   * 加载历史对话
   */
  async function loadConversation(id) {
    if (currentConversationId.value === id) return
    currentConversationId.value = id
    messages.value = []
    agentSteps.value = []

    try {
      const res = await chatApi.getConversation(id)
      const data = res.data
      if (data?.messages) {
        messages.value = data.messages.map(msg => ({
          id: msg.id,
          role: msg.role,
          content: msg.content,
          timestamp: msg.created_at,
          steps: []
        }))
      }
    } catch (error) {
      console.error('加载对话失败:', error)
    }
  }

  return {
    conversations,
    currentConversationId,
    messages,
    agentSteps,
    isStreaming,
    selectedFiles,
    workspaces,
    currentWorkspaceId,
    roadmap,
    currentConversation,
    currentWorkspace,
    hasSelectedFiles,
    sendMessage,
    sendMessageStream,
    toggleFileSelection,
    clearFileSelection,
    createNewConversation,
    loadConversation,
    fetchConversations,
    fetchWorkspaces,
    fetchRoadmap,
    setCurrentWorkspace
  }
})
