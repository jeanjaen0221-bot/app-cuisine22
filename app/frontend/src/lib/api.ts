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
