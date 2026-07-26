import request from './request'

export const systemApi = {
  /**
   * 调起系统原生目录选择器（后端 tkinter filedialog）
   * 成功返回 { path: string }；用户取消返回 { path: null }；
   * 环境不支持时后端返回 503，前端应回退到手动输入路径
   */
  pickDirectory: () => request.post('/system/pick-directory')
}
