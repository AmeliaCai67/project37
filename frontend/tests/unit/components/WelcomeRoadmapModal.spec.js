import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import WelcomeRoadmapModal from '@/components/WelcomeRoadmapModal.vue'

describe('WelcomeRoadmapModal', () => {
  let wrapper

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
      wrapper = null
    }
  })

  function mountModal(props) {
    wrapper = mount(WelcomeRoadmapModal, {
      props,
      attachTo: document.body
    })
    return wrapper
  }

  it('renders questions and tables', () => {
    mountModal({
      visible: true,
      roadmap: {
        tables: [{ name: '语文成绩.csv' }],
        relationships: [{ source: '语文成绩.csv', target: '数学成绩.csv' }],
        questions: ['相关性如何？']
      },
      workspace: { name: '期末数据' }
    })
    expect(document.body.textContent).toContain('期末数据')
    expect(document.body.textContent).toContain('语文成绩')
    expect(document.body.textContent).toContain('相关性如何？')
  })

  it('emits ask when question clicked', async () => {
    const w = mountModal({
      visible: true,
      roadmap: { questions: ['相关性如何？'] },
      workspace: { name: '期末数据' }
    })
    const btn = document.body.querySelector('.question-btn')
    btn.click()
    await w.vm.$nextTick()
    expect(w.emitted('ask')).toBeTruthy()
    expect(w.emitted('ask')[0]).toEqual(['相关性如何？'])
  })

  it('does not render when visible is false', () => {
    mountModal({
      visible: false,
      roadmap: { questions: ['Q'] },
      workspace: { name: 'x' }
    })
    expect(document.body.querySelector('.roadmap-modal-overlay')).toBeNull()
  })
})
