import axios from 'axios'

export const api = axios.create({
  baseURL: '',
})

export function fileDownload(url: string) {
  const link = document.createElement('a')
  link.href = url
  link.target = '_blank'
  document.body.appendChild(link)
  link.click()
  link.remove()
}

api.interceptors.request.use((config) => {
  try {
    // lightweight request log
    console.debug('API request', config.method?.toUpperCase(), config.url, config.params || config.data)
  } catch {}
  return config
})

api.interceptors.response.use(
  (response) => {
    try {
      console.debug('API response', response.status, response.config.url)
    } catch {}
    return response
  },
  (error) => {
    const status = error?.response?.status
    const url = error?.config?.url
    const detail = error?.response?.data?.detail || error?.response?.data?.message || error?.message || 'Erreur inconnue'
    try {
      console.error('API error', status, url, error?.response?.data || error?.message)
    } catch {}
    ;(error as any).userMessage = typeof detail === 'string' ? detail : JSON.stringify(detail)
    return Promise.reject(error)
  }
)

export async function getFloorBase() {
  const r = await api.get('/api/floorplan/base')
  return r.data
}

export async function updateFloorBase(payload: { name?: string; data?: any }) {
  const r = await api.put('/api/floorplan/base', payload)
  return r.data
}

export async function createFloorInstance(payload: { service_date: string; service_label?: string | null }) {
  const r = await api.post('/api/floorplan/instances', payload)
  return r.data
}

export async function listFloorInstances(params?: { service_date?: string; service_label?: string }) {
  const r = await api.get('/api/floorplan/instances', { params })
  return r.data
}

export async function getFloorInstance(id: string) {
  const r = await api.get(`/api/floorplan/instances/${id}`)
  return r.data
}

export async function updateFloorInstance(id: string, payload: { data?: any; assignments?: any }) {
  const r = await api.put(`/api/floorplan/instances/${id}`, payload)
  return r.data
}

export async function autoAssignInstance(id: string) {
  const r = await api.post(`/api/floorplan/instances/${id}/auto-assign`)
  return r.data
}

export async function importReservationsPdf(file: File, service_date: string, service_label?: string | null, create?: boolean) {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('service_date', service_date)
  if (service_label) fd.append('service_label', service_label)
  if (create) fd.append('create', 'true')
  const r = await api.post('/api/floorplan/import-pdf', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
  return r.data
}
