import axios from 'axios'

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api'
const client = axios.create({ baseURL })
const refreshClient = axios.create({ baseURL })
let refreshPromise = null

function clearSession() {
  localStorage.removeItem('access')
  localStorage.removeItem('refresh')
}

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    const refresh = localStorage.getItem('refresh')

    if (error.response?.status !== 401 || !original || original._retry || !refresh) {
      return Promise.reject(error)
    }

    original._retry = true
    try {
      if (!refreshPromise) {
        refreshPromise = refreshClient
          .post('/auth/token/refresh/', { refresh })
          .then(({ data }) => {
            localStorage.setItem('access', data.access)
            // The backend rotates refresh tokens and blacklists the previous one.
            if (data.refresh) localStorage.setItem('refresh', data.refresh)
            return data.access
          })
          .finally(() => { refreshPromise = null })
      }

      const access = await refreshPromise
      original.headers = original.headers || {}
      original.headers.Authorization = `Bearer ${access}`
      return client(original)
    } catch (refreshError) {
      clearSession()
      if (window.location.pathname !== '/login') window.location.href = '/login'
      return Promise.reject(refreshError)
    }
  },
)

export default client
