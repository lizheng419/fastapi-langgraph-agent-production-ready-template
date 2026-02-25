const API_BASE = '/api/v1'

let _onAuthError = null
let _authErrorPending = false

export function setAuthErrorHandler(handler) {
  _onAuthError = handler
}

/**
 * Check if an error is a network connectivity error (backend down).
 */
export function isNetworkError(err) {
  return err && (err.name === 'TypeError' || err.message === 'Failed to fetch' || err.message?.includes('NetworkError'))
}

/**
 * Wrapper around fetch that converts network failures into a clear error.
 */
async function safeFetch(url, options) {
  try {
    return await fetch(url, options)
  } catch (err) {
    throw new Error('Server is unreachable. Please check if the backend is running.')
  }
}

async function handleResponse(res) {
  if (res.status === 401) {
    if (!_authErrorPending) {
      _authErrorPending = true
      setTimeout(() => { _authErrorPending = false }, 1000)
      _onAuthError?.()
    }
    throw new Error('Session expired')
  }
  return res
}

function getHeaders(token) {
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return headers
}

/**
 * Validate that a token is still accepted by the backend.
 * Returns true if valid, false if expired/invalid or server unreachable.
 */
export async function validateToken(token) {
  try {
    const res = await safeFetch(`${API_BASE}/auth/sessions`, { headers: getHeaders(token) })
    return res.ok
  } catch {
    return false
  }
}

export async function register(email, password) {
  const res = await safeFetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) throw new Error((await res.json()).detail || 'Registration failed')
  return res.json()
}

export async function resetPassword(email, newPassword, masterPassword) {
  const body = new URLSearchParams({ email, new_password: newPassword, master_password: masterPassword })
  const res = await safeFetch(`${API_BASE}/auth/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  })
  if (!res.ok) throw new Error((await res.json()).detail || 'Password reset failed')
  return res.json()
}

export async function login(username, password) {
  const body = new URLSearchParams({ username, password, grant_type: 'password' })
  const res = await safeFetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  })
  if (!res.ok) throw new Error((await res.json()).detail || 'Login failed')
  return res.json()
}

export async function createSession(userToken) {
  const res = await handleResponse(await safeFetch(`${API_BASE}/auth/session`, {
    method: 'POST',
    headers: getHeaders(userToken),
  }))
  if (!res.ok) throw new Error('Failed to create session')
  return res.json()
}

export async function getSessions(userToken) {
  const res = await handleResponse(await safeFetch(`${API_BASE}/auth/sessions`, {
    headers: getHeaders(userToken),
  }))
  if (!res.ok) throw new Error('Failed to get sessions')
  return res.json()
}

export async function deleteSession(sessionToken, sessionId) {
  const res = await handleResponse(await safeFetch(`${API_BASE}/auth/session/${sessionId}`, {
    method: 'DELETE',
    headers: getHeaders(sessionToken),
  }))
  if (!res.ok) throw new Error('Failed to delete session')
}

/**
 * Build the chat/stream URL based on agent mode.
 * @param {'single'|'multi'|'workflow'} mode
 * @param {boolean} stream - whether this is a stream endpoint
 * @param {string|null} template - workflow template name (only for workflow mode)
 * @returns {string} full URL path
 */
function buildChatUrl(mode, stream = false, template = null) {
  const suffix = stream ? '/stream' : ''
  switch (mode) {
    case 'multi':
      return `${API_BASE}/chatbot/chat${suffix}?mode=multi`
    case 'workflow': {
      const base = `${API_BASE}/chatbot/workflow/chat${suffix}`
      return template ? `${base}?template=${encodeURIComponent(template)}` : base
    }
    case 'single':
    default:
      return `${API_BASE}/chatbot/chat${suffix}?mode=single`
  }
}

export async function sendMessage(sessionToken, messages, mode = 'single', template = null) {
  const url = buildChatUrl(mode, false, template)
  const res = await handleResponse(await safeFetch(url, {
    method: 'POST',
    headers: getHeaders(sessionToken),
    body: JSON.stringify({ messages }),
  }))
  if (!res.ok) throw new Error('Chat request failed')
  return res.json()
}

export async function streamMessage(sessionToken, messages, onChunk, onDone, mode = 'single', template = null) {
  const url = buildChatUrl(mode, true, template)
  const res = await handleResponse(await safeFetch(url, {
    method: 'POST',
    headers: getHeaders(sessionToken),
    body: JSON.stringify({ messages }),
  }))
  if (!res.ok) throw new Error('Stream request failed')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let streamDone = false

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6))
          if (data.done) {
            streamDone = true
            onDone?.()
          } else if (data.content) {
            onChunk(data.content)
          }
        } catch { }
      }
    }
  }
  if (!streamDone) onDone?.()
}

export async function getMessages(sessionToken, mode = 'single') {
  const url = `${API_BASE}/chatbot/messages`
  const res = await handleResponse(await safeFetch(url, {
    headers: getHeaders(sessionToken),
  }))
  if (!res.ok) throw new Error('Failed to get messages')
  return res.json()
}

export async function getWorkflowTemplates(sessionToken) {
  const res = await handleResponse(await safeFetch(`${API_BASE}/chatbot/workflow/templates`, {
    headers: getHeaders(sessionToken),
  }))
  if (!res.ok) throw new Error('Failed to get workflow templates')
  return res.json()
}

export async function getPendingApprovals(sessionToken) {
  const res = await handleResponse(await safeFetch(`${API_BASE}/approvals/pending`, {
    headers: getHeaders(sessionToken),
  }))
  if (!res.ok) throw new Error('Failed to get approvals')
  return res.json()
}

export async function approveRequest(sessionToken, requestId, comment) {
  const res = await handleResponse(await safeFetch(`${API_BASE}/approvals/${requestId}/approve`, {
    method: 'POST',
    headers: getHeaders(sessionToken),
    body: JSON.stringify({ comment }),
  }))
  if (!res.ok) throw new Error('Approve failed')
  return res.json()
}

export async function rejectRequest(sessionToken, requestId, comment) {
  const res = await handleResponse(await safeFetch(`${API_BASE}/approvals/${requestId}/reject`, {
    method: 'POST',
    headers: getHeaders(sessionToken),
    body: JSON.stringify({ comment }),
  }))
  if (!res.ok) throw new Error('Reject failed')
  return res.json()
}

// --- RAG Document Management ---

export async function uploadDocument(token, file) {
  const formData = new FormData()
  formData.append('file', file)
  const headers = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await handleResponse(await safeFetch(`${API_BASE}/rag/upload`, {
    method: 'POST',
    headers,
    body: formData,
  }))
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Upload failed')
  }
  return res.json()
}

export async function getDocuments(token) {
  const res = await handleResponse(await safeFetch(`${API_BASE}/rag/documents`, {
    headers: getHeaders(token),
  }))
  if (!res.ok) throw new Error('Failed to get documents')
  return res.json()
}

export async function deleteDocument(token, docId) {
  const res = await handleResponse(await safeFetch(`${API_BASE}/rag/documents/${docId}`, {
    method: 'DELETE',
    headers: getHeaders(token),
  }))
  if (!res.ok) throw new Error('Failed to delete document')
  return res.json()
}
