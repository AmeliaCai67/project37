/**
 * 去掉文件名/表名开头的时间戳前缀（格式：YYYYMMDD_HHMMSS_）。
 * 后端存储的文件名/表名带时间戳前缀（如 20260719_203000_成绩表.csv），
 * 前端展示时统一隐藏，后端数据不动。
 *
 * @param {string|null|undefined} name 原始名称
 * @returns {string} 去掉前缀后的名称（仅当完整匹配 8 位日期_6 位时间_ 才剥离）
 */
export function stripTimestampPrefix(name) {
  if (name == null) return ''
  return String(name).replace(/^\d{8}_\d{6}_/, '')
}
