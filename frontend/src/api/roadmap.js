import request from './request'

export const roadmapApi = {
  // force=true 时后端忽略缓存强制重建画像与推荐问题（「重新分析数据关系」用）
  get: (workspaceId, force = false) =>
    request.get(`/workspaces/${workspaceId}/roadmap`, { params: force ? { force: true } : {} })
}
