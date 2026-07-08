import { apiFetch } from './http'

export async function invokeTransform(payload) {
  return apiFetch('/llm/invoke', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function getJobStatus(jobId) {
  return apiFetch(`/llm/check_status_view/${jobId}`)
}

export async function cancelJob(jobId) {
  return apiFetch(`/llm/jobs/${jobId}/cancel`, { method: 'POST' })
}

export async function getJobResults(jobId, page = 1, pageSize = 50) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })

  return apiFetch(`/api/jobs/${jobId}/results?${params}`)
}
