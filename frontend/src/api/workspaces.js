import request from './request'

export const workspacesApi = {
  list: () => request.get('/workspaces/list'),
  mount: (data) => request.post('/workspaces/mount', data),
  unmount: (id) => request.post(`/workspaces/${id}/unmount`),
  updateOutputPath: (id, outputPath) => request.put(`/workspaces/${id}/output-path`, { output_path: outputPath })
}
