async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    credentials: 'include',
    headers: {
      ...(options.body && !(options.body instanceof FormData)
        ? { 'Content-Type': 'application/json' }
        : {}),
      ...options.headers,
    },
  })

  if (response.status === 204) {
    return null
  }

  const result = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = Array.isArray(result.detail)
      ? result.detail.map((issue) => issue.msg).join(' ')
      : result.detail
    const error = new Error(detail || `Request failed (${response.status}).`)
    error.status = response.status
    throw error
  }
  return result
}

export const api = {
  register: (data) =>
    request('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  login: (data) =>
    request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  me: () => request('/api/auth/me'),
  dashboard: () => request('/api/dashboard'),
  detections: () => request('/api/detections'),
  detection: (id) => request(`/api/detections/${id}`),
  classifications: () => request('/api/classifications'),
  classification: (id) => request(`/api/classifications/${id}`),
  classify: (image) => {
    const formData = new FormData()
    formData.append('image', image)
    return request('/api/classifications', {
      method: 'POST',
      body: formData,
    })
  },
  detect: (image) => {
    const formData = new FormData()
    formData.append('image', image)
    return request('/api/detections', {
      method: 'POST',
      body: formData,
    })
  },
}
