import { describe, it, expect } from 'vitest'
import { mount, config } from '@vue/test-utils'
import { setActivePinia } from 'pinia'
import { useChatStore } from '@/stores/chat'
import RecommendedQuestions from '@/components/RecommendedQuestions.vue'

const globalPinia = config.global.plugins[0]

describe('RecommendedQuestions', () => {
  it('renders questions from roadmap', () => {
    setActivePinia(globalPinia)
    const store = useChatStore()
    store.roadmap = { questions: ['A 和 B 的关系？', '谁的总分最高？'] }

    const wrapper = mount(RecommendedQuestions)
    expect(wrapper.text()).toContain('A 和 B 的关系？')
    expect(wrapper.text()).toContain('谁的总分最高？')
  })
})
