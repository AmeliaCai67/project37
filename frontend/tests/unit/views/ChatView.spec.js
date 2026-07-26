import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ChatView from '@/views/ChatView.vue'

const mockFetchRoadmap = vi.fn(() => Promise.resolve())
const mockPush = vi.fn()

const chatStore = {
  conversations: [],
  messages: [],
  currentConversationId: null,
  currentWorkspaceId: 2,
  currentWorkspace: { id: 2, name: '期末数据', type: 'external', output_path: '/out/2' },
  selectedFiles: [],
  isStreaming: false,
  agentSteps: [],
  pendingRoadmapModal: false,
  roadmap: {
    questions: [
      { question: '问题一：各产品类别的销售额排名如何？', type: '排名分析', tables: [] },
      { question: '问题二：订单数量随时间的趋势如何？', type: '趋势分析', tables: [] },
      { question: '问题三：运费与商品价格有什么关系？', type: '关联分析', tables: [] },
      { question: '问题四：不应该显示出来', type: '对比分析', tables: [] }
    ]
  },
  fetchConversations: vi.fn(() => Promise.resolve()),
  fetchWorkspaces: vi.fn(() => Promise.resolve()),
  fetchRoadmap: mockFetchRoadmap,
  loadConversation: vi.fn(),
  createNewConversation: vi.fn(),
  sendMessageStream: vi.fn(),
  toggleFileSelection: vi.fn()
}

vi.mock('@/stores/chat.js', () => ({
  useChatStore: () => chatStore
}))

vi.mock('@/stores/user.js', () => ({
  useUserStore: () => ({ isReadonly: false })
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: {} }),
  useRouter: () => ({ push: mockPush })
}))

vi.mock('@/api/files', () => ({
  filesApi: { getList: vi.fn(() => Promise.resolve({ data: [] })) }
}))

const globalConfig = {
  global: {
    stubs: {
      AgentSteps: true,
      WorkspaceNotes: true,
      WelcomeRoadmapModal: true
    }
  }
}

describe('ChatView 欢迎页推荐问题卡片', () => {
  beforeEach(() => {
    // 避免 WelcomeRoadmapModal 逻辑干扰（今天不再提示）
    localStorage.setItem(`hide_welcome_roadmap_${new Date().toISOString().slice(0, 10)}`, '1')
    mockFetchRoadmap.mockClear()
  })

  it('横排展示最多 3 张推荐问题卡片，类型作为卡片标题', () => {
    const wrapper = mount(ChatView, globalConfig)
    const cards = wrapper.findAll('.finding-card')
    expect(cards).toHaveLength(3)
    expect(cards[0].find('.card-title').text()).toBe('排名分析')
    expect(cards[0].find('.card-desc').text()).toContain('问题一')
    expect(wrapper.text()).not.toContain('问题四')
  })

  it('点击推荐问题卡片填入输入框但不直接发送', async () => {
    const wrapper = mount(ChatView, globalConfig)
    await wrapper.findAll('.finding-card')[1].trigger('click')
    const textarea = wrapper.find('textarea')
    expect(textarea.element.value).toBe('问题二：订单数量随时间的趋势如何？')
    expect(chatStore.sendMessageStream).not.toHaveBeenCalled()
  })

  it('「重新分析数据关系」按钮强制刷新 roadmap，期间显示分析中并禁用', async () => {
    let resolve
    mockFetchRoadmap.mockReturnValueOnce(new Promise(r => { resolve = r }))
    const wrapper = mount(ChatView, globalConfig)
    await flushPromises()
    mockFetchRoadmap.mockClear()

    const btn = wrapper.find('.refresh-roadmap')
    expect(btn.text()).toBe('重新分析数据关系')
    await btn.trigger('click')
    expect(mockFetchRoadmap).toHaveBeenCalledWith(true)
    expect(wrapper.find('.refresh-roadmap').text()).toBe('分析中…')
    expect(wrapper.find('.refresh-roadmap').attributes('disabled')).toBeDefined()

    resolve()
    await flushPromises()
    expect(wrapper.find('.refresh-roadmap').text()).toBe('重新分析数据关系')
  })

  it('无推荐问题时隐藏卡片与刷新按钮', async () => {
    chatStore.roadmap = { questions: [] }
    const wrapper = mount(ChatView, globalConfig)
    await flushPromises()
    expect(wrapper.find('.finding-card').exists()).toBe(false)
    expect(wrapper.find('.refresh-roadmap').exists()).toBe(false)
  })
})

describe('ChatView 会话列表时间分组', () => {
  const daysAgo = n => new Date(Date.now() - n * 86400000).toISOString()

  beforeEach(() => {
    localStorage.setItem(`hide_welcome_roadmap_${new Date().toISOString().slice(0, 10)}`, '1')
    chatStore.roadmap = { questions: [] }
    chatStore.conversations = [
      { id: 1, title: '本周的对话', updated_at: daysAgo(0) },
      { id: 2, title: '较早的对话A', updated_at: daysAgo(25) },   // 一定不在本周
      { id: 3, title: '较早的对话B', updated_at: daysAgo(200) },  // 一定不在本月
      { id: 4, title: '很早的对话', updated_at: daysAgo(400) }    // 一定不在本年
    ]
  })

  afterEach(() => {
    chatStore.conversations = []
  })

  it('按时间分组展示，默认只展开「本周」', () => {
    const wrapper = mount(ChatView, globalConfig)
    const headers = wrapper.findAll('.conv-group-header')
    expect(headers.length).toBeGreaterThanOrEqual(3)
    expect(headers[0].text()).toContain('本周')

    // 默认仅本周展开：只有本周的对话可见
    expect(wrapper.text()).toContain('本周的对话')
    expect(wrapper.text()).not.toContain('较早的对话A')
    expect(wrapper.text()).not.toContain('很早的对话')
  })

  it('点击分组头展开/收起对应会话', async () => {
    const wrapper = mount(ChatView, globalConfig)
    // 展开最后一个分组（更早）
    const headers = wrapper.findAll('.conv-group-header')
    const earlierHeader = headers[headers.length - 1]
    expect(earlierHeader.text()).toContain('更早')
    await earlierHeader.trigger('click')
    expect(wrapper.text()).toContain('很早的对话')

    // 收起「本周」
    await wrapper.findAll('.conv-group-header')[0].trigger('click')
    expect(wrapper.text()).not.toContain('本周的对话')
  })
})
