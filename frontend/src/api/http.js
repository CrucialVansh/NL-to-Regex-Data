const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export class ApiError extends Error {
  constructor(message, { status, data } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

export async function parseJsonResponse(response) {
  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new ApiError(data.error || data.message || `Request failed (${response.status})`, {
      status: response.status,
      data,
    })
  }

  return data
}

export async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options)
  return parseJsonResponse(response)
}

export async function apiFetchWithAccepted(response) {
  const data = await response.json().catch(() => ({}))

  if (response.status === 202) {
    return { ...data, status: data.status ?? 'processing' }
  }

  if (!response.ok) {
    throw new ApiError(data.error || data.message || `Request failed (${response.status})`, {
      status: response.status,
      data,
    })
  }

  return data
}
