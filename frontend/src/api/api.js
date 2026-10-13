// All API requests use cookie credentials; the session cookie is HttpOnly.
//
// Production: the browser calls /api/... on the SAME origin as the site. Vercel
// forwards those calls to the backend (see frontend/vercel.json), so the login
// cookie is first-party and works in every browser. Do NOT set VITE_API_URL in
// production - it is only honoured in local development.
const BASE_URL = (import.meta.env.DEV
  ? (import.meta.env.VITE_API_URL || 'http://localhost:8000')
  : window.location.origin
).replace(/\/$/, '')
let csrfToken = ''

export function setCsrfToken(value) {
  csrfToken = value || ''
}

class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

async function request(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase()
  const headers = { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(options.headers || {}) }
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && csrfToken) headers['X-CSRF-Token'] = csrfToken

  let res
  try {
    res = await fetch(`${BASE_URL}${path}`, { ...options, method, headers, credentials: 'include' })
  } catch {
    throw new ApiError('Unable to reach LeetTrack API. Check the backend URL and whether the service is awake.', 0)
  }

  let body = null
  try { body = await res.json() } catch {}
  if (!res.ok) {
    if (res.status === 401 && !['/api/auth/login', '/api/auth/register', '/api/auth/me'].includes(path)) {
      setCsrfToken('')
      if (typeof window !== 'undefined') window.dispatchEvent(new Event('leettrack:unauthorized'))
    }
    if (!body && [502, 503, 504].includes(res.status)) {
      throw new ApiError('The server is waking up (free hosting sleeps when idle). Please wait about a minute and try again.', res.status)
    }
    const detail = Array.isArray(body?.detail) ? body.detail.map(d => d.msg).join(' ') : body?.detail
    throw new ApiError(detail || `Request failed (${res.status})`, res.status)
  }
  return body
}

export async function register({ username, email, password }) {
  const data = await request('/api/auth/register', { method: 'POST', body: JSON.stringify({ username, email, password }) })
  setCsrfToken(data.csrf_token)
  return data.user
}
export async function login({ email, password }) {
  const data = await request('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
  setCsrfToken(data.csrf_token)
  return data.user
}
export async function getSession() {
  const data = await request('/api/auth/me')
  setCsrfToken(data.csrf_token)
  return data.user
}
export async function logout() {
  try { await request('/api/auth/logout', { method: 'POST' }) } finally { setCsrfToken('') }
}
export function getUser() { return request('/api/me') }
export function getDailyPlan(simulatedDate) {
  const query = simulatedDate ? `?simulated_date=${encodeURIComponent(simulatedDate)}` : ''
  return request(`/api/me/daily-plan${query}`)
}
export function completeQuestion({ question_id, platform, difficulty }) {
  return request('/api/questions/complete', { method: 'POST', body: JSON.stringify({ question_id, platform, difficulty }) })
}
export function completeRevision({ question_id, platform, difficulty, revision_counter }) {
  return request('/api/revisions/complete', { method: 'POST', body: JSON.stringify({ question_id, platform, difficulty, revision_counter }) })
}
export function getSolvedQuestions() { return request('/api/me/solved') }
export function getUpcomingRevisions() { return request('/api/me/revisions') }
export function getQuestions(filters = {}) {
  const params = new URLSearchParams()
  if (filters.difficulty) params.set('difficulty', filters.difficulty)
  if (filters.topic) params.set('topic', filters.topic)
  if (filters.platform) params.set('platform', filters.platform)
  const query = params.toString()
  return request(`/api/questions${query ? `?${query}` : ''}`)
}
export function getProgress() { return request('/api/me/progress') }
export { ApiError }
