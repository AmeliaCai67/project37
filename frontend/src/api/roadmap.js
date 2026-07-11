import request from './request'

export const roadmapApi = {
  get: (workspaceId) => request.get(`/workspaces/${workspaceId}/roadmap`)
}
