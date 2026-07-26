import request from './request'

export const workspacesApi = {
  list: () => request.get('/workspaces/list'),
  mount: (data) => request.post('/workspaces/mount', data),
  unmount: (id) => request.post(`/workspaces/${id}/unmount`),
  // 实时同步 external 空间源文件夹（快速返回，提取走后台），切换空间/进文件页时触发
  sync: (id) => request.post(`/workspaces/${id}/sync`),
  updateOutputPath: (id, outputPath) => request.put(`/workspaces/${id}/output-path`, { output_path: outputPath })
}
