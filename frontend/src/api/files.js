import request from './request'

export const filesApi = {
  /**
   * 获取文件列表
   */
  getList(params = {}) {
    return request.get('/files/list', { params })
  },

  /**
   * 上传文件
   */
  upload(file, workspaceId, onProgress) {
    const formData = new FormData()
    formData.append('file', file)
    if (workspaceId) {
      formData.append('workspace_id', workspaceId)
    }

    return request.post('/files/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress) {
          const percent = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          )
          onProgress(percent)
        }
      }
    })
  },

  /**
   * 删除文件
   */
  delete(id) {
    return request.delete(`/files/${id}`)
  },

  /**
   * 获取文件内容预览
   */
  getPreview(id, params = {}) {
    return request.get(`/files/${id}/preview`, { params })
  }
}
