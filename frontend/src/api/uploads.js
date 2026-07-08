import { apiFetch, apiFetchWithAccepted } from './http'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export async function listUploads() {
  const data = await apiFetch('/api/uploads')
  return data.uploads ?? []
}

export async function uploadFile(file) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE}/api/upload`, {
    method: 'POST',
    body: formData,
  })

  return apiFetchWithAccepted(response)
}

export async function getUploadStatus(uploadedFileId) {
  const response = await fetch(`${API_BASE}/api/uploads/${uploadedFileId}/status`)
  return apiFetchWithAccepted(response)
}

export async function getUploadData(uploadedFileId, page = 1, pageSize = 50) {
  return apiFetch(`/api/uploads/${uploadedFileId}/data?page=${page}&page_size=${pageSize}`)
}
