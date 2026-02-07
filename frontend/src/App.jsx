import { useState, useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import ChatPage from './pages/ChatPage'
import ApprovalsPage from './pages/ApprovalsPage'
import { setAuthErrorHandler, validateToken } from './api'

export default function App() {
  const [auth, setAuth] = useState(() => {
    const saved = localStorage.getItem('auth')
    return saved ? JSON.parse(saved) : null
  })
  const [validating, setValidating] = useState(true)

  useEffect(() => {
    if (auth) localStorage.setItem('auth', JSON.stringify(auth))
    else localStorage.removeItem('auth')
  }, [auth])

  const logout = () => setAuth(null)

  useEffect(() => {
    setAuthErrorHandler(logout)
  }, [])

  useEffect(() => {
    if (!auth?.userToken) {
      setValidating(false)
      return
    }
    validateToken(auth.userToken).then((valid) => {
      if (!valid) setAuth(null)
      setValidating(false)
    })
  }, [])

  if (validating) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-4 border-blue-400 border-t-transparent rounded-full" />
      </div>
    )
  }

  if (!auth) return <LoginPage onAuth={setAuth} />

  return (
    <Routes>
      <Route path="/" element={<ChatPage auth={auth} setAuth={setAuth} onLogout={logout} />} />
      <Route path="/approvals" element={<ApprovalsPage auth={auth} onLogout={logout} />} />
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  )
}
