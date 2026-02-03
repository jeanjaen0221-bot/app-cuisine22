import axios, { AxiosRequestHeaders } from 'axios'

export const api = axios.create({
  baseURL: '',
})

let _salleDebug = false
export function setSalleDebug(v: boolean) { _salleDebug = v }

export function fileDownload(data: Blob | string, filename?: string) {
  const link = document.createElement('a')
  if (data instanceof Blob) {
    link.href = URL.createObjectURL(data)
    link.download = filename || 'download.pdf'
  } else {
    link.href = data
    link.target = '_blank'
    link.download = filename || ''
  }
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  if (data instanceof Blob) {
    setTimeout(() => URL.revokeObjectURL(link.href), 100)
  }
}

api.interceptors.request.use((config) => {
  try {
    // lightweight request log
    console.debug('API request', config.method?.toUpperCase(), config.url, config.params || config.data)
    // Ensure headers object exists with a compatible type
    if (!config.headers) (config as any).headers = {} as AxiosRequestHeaders
    if (_salleDebug) {
      ;(config.headers as any)['X-Salle-Debug'] = '1'
    } else {
      try { delete (config.headers as any)['X-Salle-Debug'] } catch {}
    }
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

export async function listFloorBases() {
  // Backend only has single base, return as array for compatibility
  const r = await api.get('/api/floorplan/base')
  return [r.data]
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

// ----- Numbering & PDF -----

export async function numberBaseTables() {
  const r = await api.post('/api/floorplan/base/number-tables')
  return r.data
}

export async function exportBasePdf() {
  const r = await api.get('/api/floorplan/base/export-pdf', { responseType: 'blob' })
  const blob = new Blob([r.data], { type: 'application/pdf' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'base_floorplan.pdf'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export async function numberInstanceTables(id: string) {
  const r = await api.post(`/api/floorplan/instances/${id}/number-tables`)
  return r.data
}

export async function exportInstancePdf(id: string) {
  const r = await api.get(`/api/floorplan/instances/${id}/export-pdf`, { responseType: 'blob' })
  const blob = new Blob([r.data], { type: 'application/pdf' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'floorplan_instance.pdf'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export async function exportInstanceAnnotatedPdf(
  id: string,
  file: File,
  opts?: { page_start?: number; start_y_mm?: number; row_h_mm?: number; table_x_mm?: number }
) {
  const fd = new FormData()
  fd.append('file', file)
  if (opts?.page_start != null) fd.append('page_start', String(opts.page_start))
  if (opts?.start_y_mm != null) fd.append('start_y_mm', String(opts.start_y_mm))
  if (opts?.row_h_mm != null) fd.append('row_h_mm', String(opts.row_h_mm))
  if (opts?.table_x_mm != null) fd.append('table_x_mm', String(opts.table_x_mm))
  const r = await api.post(`/api/floorplan/instances/${id}/export-annotated`, fd, { responseType: 'blob' })
  const blob = new Blob([r.data], { type: 'application/pdf' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'floorplan_instance_annotated.pdf'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
