import { describe, it, expect } from 'vitest'
import { stripTimestampPrefix } from '@/utils/display'

describe('stripTimestampPrefix', () => {
  it('去掉标准时间戳前缀', () => {
    expect(stripTimestampPrefix('20260718_225124_olist_orders_dataset')).toBe('olist_orders_dataset')
  })

  it('无前缀时原样返回', () => {
    expect(stripTimestampPrefix('olist_orders_dataset')).toBe('olist_orders_dataset')
  })

  it('部分匹配不剥离（非完整 8 位日期_6 位时间）', () => {
    expect(stripTimestampPrefix('2026071_225124_orders')).toBe('2026071_225124_orders')
    expect(stripTimestampPrefix('20260718_22512_orders')).toBe('20260718_22512_orders')
  })

  it('纯数字名不带下划线后缀时不剥离', () => {
    expect(stripTimestampPrefix('20260718')).toBe('20260718')
  })

  it('处理 null/undefined/非字符串', () => {
    expect(stripTimestampPrefix(null)).toBe('')
    expect(stripTimestampPrefix(undefined)).toBe('')
    expect(stripTimestampPrefix(123)).toBe('123')
  })
})
