import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Send, LogOut, ShieldCheck, User, Loader2, Plus, Globe, ChevronDown, Zap, Users, Workflow, Cpu, MessageSquare, Trash2, PanelLeftClose, PanelLeft, WifiOff, RefreshCw, FileText } from 'lucide-react'
import { streamMessage, createSession, getWorkflowTemplates, getMessages, getSessions, deleteSession, isNetworkError } from '../api'
import { useLanguage } from '../i18n/LanguageContext'
import MarkdownRenderer from '../components/MarkdownRenderer'

const AGENT_MODES = [
  { id: 'single', icon: Zap, color: 'bg-blue-600' },
  { id: 'multi', icon: Users, color: 'bg-purple-600' },
  { id: 'workflow', icon: Workflow, color: 'bg-amber-600' },
]

export default function ChatPage({ auth, setAuth, onLogout }) {
  const { t, lang, switchLang } = useLanguage()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [agentMode, setAgentMode] = useState(() => localStorage.getItem('agentMode') || 'single')
  const [showModeMenu, setShowModeMenu] = useState(false)
  const [workflowTemplate, setWorkflowTemplate] = useState('')
  const [workflowTemplates, setWorkflowTemplates] = useState([])
  const [sessions, setSessions] = useState([])
  const [sidebarOpen, setSidebarOpen] = useState(() => localStorage.getItem('sidebarOpen') !== 'false')
  const [connectionError, setConnectionError] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const modeMenuRef = useRef(null)
  const retryTimerRef = useRef(null)
  const navigate = useNavigate()

  const currentMode = AGENT_MODES.find((m) => m.id === agentMode) || AGENT_MODES[0]

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    localStorage.setItem('agentMode', agentMode)
  }, [agentMode])

  useEffect(() => {
    localStorage.setItem('sidebarOpen', sidebarOpen)
  }, [sidebarOpen])

  const loadInitialData = () => {
    getMessages(auth.sessionToken, agentMode)
      .then((data) => {
        const msgs = data.messages || data || []
        if (msgs.length > 0) setMessages(msgs)
        setConnectionError(false)
      })
      .catch((err) => {
        if (isNetworkError(err) || err.message?.includes('unreachable')) setConnectionError(true)
      })

    if (auth.userToken) {
      getSessions(auth.userToken)
        .then((data) => {
          setSessions(Array.isArray(data) ? data : [])
          setConnectionError(false)
        })
        .catch((err) => {
          if (isNetworkError(err) || err.message?.includes('unreachable')) setConnectionError(true)
        })
    }
  }

  useEffect(() => {
    if (agentMode === 'workflow') {
      getWorkflowTemplates(auth.sessionToken)
        .then((data) => {
          setWorkflowTemplates(data.templates || data || [])
          setConnectionError(false)
        })
        .catch((err) => {
          if (isNetworkError(err) || err.message?.includes('unreachable')) setConnectionError(true)
          else setWorkflowTemplates([])
        })
    }
  }, [agentMode, auth.sessionToken])

  useEffect(() => {
    loadInitialData()
  }, [auth.sessionToken])

  useEffect(() => {
    if (auth.userToken) {
      getSessions(auth.userToken)
        .then((data) => setSessions(Array.isArray(data) ? data : []))
        .catch(() => setSessions([]))
    }
  }, [auth.sessionId])

  useEffect(() => {
    if (!connectionError) {
      if (retryTimerRef.current) clearInterval(retryTimerRef.current)
      retryTimerRef.current = null
      return
    }
    retryTimerRef.current = setInterval(() => {
      loadInitialData()
    }, 5000)
    return () => {
      if (retryTimerRef.current) clearInterval(retryTimerRef.current)
    }
  }, [connectionError])

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (modeMenuRef.current && !modeMenuRef.current.contains(e.target)) {
        setShowModeMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleModeChange = (modeId) => {
    setAgentMode(modeId)
    setShowModeMenu(false)
    if (modeId !== 'workflow') setWorkflowTemplate('')
  }

  const handleSend = async () => {
    const text = input.trim()
    if (!text || streaming) return

    const userMsg = { role: 'user', content: text }
    const updatedMessages = [...messages, userMsg]
    setMessages(updatedMessages)
    setInput('')
    setStreaming(true)

    setMessages((prev) => [...prev, { role: 'assistant', content: '' }])

    try {
      await streamMessage(
        auth.sessionToken,
        updatedMessages.map((m) => ({ role: m.role, content: m.content })),
        (chunk) => {
          setMessages((prev) => {
            const copy = [...prev]
            const last = copy[copy.length - 1]
            if (last.role === 'assistant') {
              copy[copy.length - 1] = { ...last, content: last.content + chunk }
            }
            return copy
          })
        },
        () => setStreaming(false),
        agentMode,
        workflowTemplate || null,
      )
    } catch (err) {
      const isOffline = isNetworkError(err) || err.message?.includes('unreachable')
      if (isOffline) setConnectionError(true)
      setMessages((prev) => {
        const copy = [...prev]
        copy[copy.length - 1] = {
          role: 'assistant',
          content: isOffline
            ? 'Unable to reach the server. The backend may be restarting — your message will not be lost, please try again shortly.'
            : `Error: ${err.message}`,
        }
        return copy
      })
      setStreaming(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleNewChat = async () => {
    try {
      const session = await createSession(auth.userToken)
      const updatedAuth = {
        ...auth,
        sessionToken: session.token.access_token,
        sessionId: session.session_id,
      }
      setAuth(updatedAuth)
      setMessages([])
      setConnectionError(false)
    } catch (err) {
      if (isNetworkError(err) || err.message?.includes('unreachable')) setConnectionError(true)
    }
  }

  const switchSession = (sess) => {
    const updatedAuth = {
      ...auth,
      sessionToken: sess.token.access_token,
      sessionId: sess.session_id,
    }
    setAuth(updatedAuth)
    setMessages([])
  }

  const handleDeleteSession = async (e, sess) => {
    e.stopPropagation()
    if (sess.session_id === auth.sessionId) return
    try {
      await deleteSession(sess.token.access_token, sess.session_id)
      setSessions((prev) => prev.filter((s) => s.session_id !== sess.session_id))
    } catch { }
  }

  const ModeIcon = currentMode.icon

  return (
    <div className="h-screen flex bg-gray-50">
      {/* Sidebar */}
      {sidebarOpen && (
        <aside className="w-64 bg-gray-900 text-white flex flex-col shrink-0">
          <div className="p-3 flex items-center justify-between border-b border-gray-700">
            <span className="text-sm font-semibold">{t('sidebar.sessions')}</span>
            <div className="flex items-center gap-1">
              <button onClick={handleNewChat} className="p-1.5 hover:bg-gray-700 rounded-lg transition-colors" title={t('chat.newChat')}>
                <Plus className="w-4 h-4" />
              </button>
              <button onClick={() => setSidebarOpen(false)} className="p-1.5 hover:bg-gray-700 rounded-lg transition-colors">
                <PanelLeftClose className="w-4 h-4" />
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {sessions.map((sess) => (
              <button
                key={sess.session_id}
                onClick={() => switchSession(sess)}
                className={`w-full text-left px-3 py-2.5 rounded-lg text-sm flex items-center gap-2 group transition-colors ${sess.session_id === auth.sessionId ? 'bg-gray-700 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
                  }`}
              >
                <MessageSquare className="w-3.5 h-3.5 shrink-0" />
                <span className="flex-1 truncate">{sess.name || sess.session_id.slice(0, 8)}</span>
                {sess.session_id !== auth.sessionId && (
                  <Trash2
                    className="w-3.5 h-3.5 opacity-0 group-hover:opacity-60 hover:!opacity-100 shrink-0 text-gray-500 hover:text-red-400 transition-all"
                    onClick={(e) => handleDeleteSession(e, sess)}
                  />
                )}
              </button>
            ))}
            {sessions.length === 0 && (
              <p className="text-xs text-gray-600 text-center py-4">{t('sidebar.noSessions')}</p>
            )}
          </div>
          <div className="p-3 border-t border-gray-700 space-y-1">
            <button
              onClick={() => navigate('/knowledge')}
              className="w-full px-3 py-2 text-sm text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg flex items-center gap-2 transition-colors"
            >
              <FileText className="w-4 h-4" /> {t('chat.knowledge')}
            </button>
            <button
              onClick={() => navigate('/approvals')}
              className="w-full px-3 py-2 text-sm text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg flex items-center gap-2 transition-colors"
            >
              <ShieldCheck className="w-4 h-4" /> {t('chat.approvals')}
            </button>
            <div className="flex items-center justify-between px-3 py-1">
              <span className="text-xs text-gray-500 truncate">{auth.email}</span>
              <button onClick={onLogout} className="p-1 text-gray-500 hover:text-red-400 transition-colors" title={t('chat.logout')}>
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </aside>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="bg-white border-b border-gray-200 px-4 py-2.5 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            {!sidebarOpen && (
              <button onClick={() => setSidebarOpen(true)} className="p-2 text-gray-400 hover:text-gray-700 rounded-lg hover:bg-gray-100 transition-colors">
                <PanelLeft className="w-4 h-4" />
              </button>
            )}
            <div className={`w-8 h-8 ${currentMode.color} rounded-lg flex items-center justify-center transition-colors`}>
              <ModeIcon className="w-4 h-4 text-white" />
            </div>
            <div>
              <h1 className="text-sm font-semibold text-gray-900">{t('chat.title')}</h1>
              <p className="text-[11px] text-gray-500">{t('chat.subtitle')}</p>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            {/* Agent Mode Selector */}
            <div className="relative" ref={modeMenuRef}>
              <button
                onClick={() => setShowModeMenu(!showModeMenu)}
                className="px-2.5 py-1.5 text-xs text-gray-700 hover:bg-gray-100 rounded-lg flex items-center gap-1.5 transition-colors border border-gray-200"
              >
                <ModeIcon className="w-3.5 h-3.5" />
                <span className="font-medium">{t(`chat.mode.${agentMode}`)}</span>
                <ChevronDown className={`w-3 h-3 transition-transform ${showModeMenu ? 'rotate-180' : ''}`} />
              </button>
              {showModeMenu && (
                <div className="absolute right-0 top-full mt-1 w-64 bg-white border border-gray-200 rounded-xl shadow-lg py-1.5 z-50">
                  {AGENT_MODES.map((mode) => {
                    const Icon = mode.icon
                    return (
                      <button
                        key={mode.id}
                        onClick={() => handleModeChange(mode.id)}
                        className={`w-full px-4 py-2.5 text-left flex items-center gap-3 hover:bg-gray-50 transition-colors ${agentMode === mode.id ? 'bg-blue-50' : ''}`}
                      >
                        <div className={`w-7 h-7 ${mode.color} rounded-lg flex items-center justify-center`}>
                          <Icon className="w-3.5 h-3.5 text-white" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-900">{t(`chat.mode.${mode.id}`)}</div>
                          <div className="text-xs text-gray-500 truncate">{t(`chat.modeDesc.${mode.id}`)}</div>
                        </div>
                        {agentMode === mode.id && (
                          <div className="w-2 h-2 bg-blue-600 rounded-full shrink-0" />
                        )}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
            {/* Workflow Template Selector */}
            {agentMode === 'workflow' && (
              <select
                value={workflowTemplate}
                onChange={(e) => setWorkflowTemplate(e.target.value)}
                className="px-2.5 py-1.5 text-xs text-gray-700 border border-gray-200 rounded-lg bg-white hover:bg-gray-50 transition-colors outline-none focus:border-amber-400"
              >
                <option value="">{t('chat.workflowAuto')}</option>
                {workflowTemplates.map((tpl) => (
                  <option key={tpl.name || tpl} value={tpl.name || tpl}>
                    {tpl.name || tpl}
                  </option>
                ))}
              </select>
            )}
            <div className="w-px h-5 bg-gray-200" />
            <button
              onClick={() => switchLang(lang === 'zh' ? 'en' : 'zh')}
              className="px-2.5 py-1.5 text-xs text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded-lg flex items-center gap-1 transition-colors"
            >
              <Globe className="w-3.5 h-3.5" /> {t(`language.${lang === 'zh' ? 'en' : 'zh'}`)}
            </button>
            <div className="w-px h-5 bg-gray-200" />
            <button
              onClick={onLogout}
              className="px-2.5 py-1.5 text-xs text-gray-500 hover:text-red-500 hover:bg-red-50 rounded-lg flex items-center gap-1 transition-colors"
              title={t('chat.logout')}
            >
              <LogOut className="w-3.5 h-3.5" /> {t('chat.logout')}
            </button>
          </div>
        </header>

        {/* Connection Error Banner */}
        {connectionError && (
          <div className="bg-amber-50 border-b border-amber-200 px-4 py-2.5 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2 text-amber-700 text-sm">
              <WifiOff className="w-4 h-4" />
              <span>{t('chat.connectionError') || 'Cannot reach server. Retrying automatically...'}</span>
            </div>
            <button
              onClick={loadInitialData}
              className="flex items-center gap-1 text-xs text-amber-600 hover:text-amber-800 px-2 py-1 rounded hover:bg-amber-100 transition-colors"
            >
              <RefreshCw className="w-3 h-3" /> {t('chat.retry') || 'Retry'}
            </button>
          </div>
        )}

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <div className="h-full flex items-center justify-center">
              <div className="text-center max-w-lg px-4">
                <div className={`w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-6 ${currentMode.color} bg-opacity-15`}>
                  <ModeIcon className={`w-8 h-8 ${currentMode.color.replace('bg-', 'text-')}`} />
                </div>
                <h2 className="text-2xl font-semibold text-gray-900 mb-2">{t('chat.welcomeTitle')}</h2>
                <p className="text-gray-500 mb-2">
                  {t('chat.welcomeSubtitle')}
                </p>
                <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-gray-100 rounded-full text-xs text-gray-600 mb-8">
                  <ModeIcon className="w-3.5 h-3.5" />
                  {t(`chat.mode.${agentMode}`)}
                  {agentMode === 'workflow' && workflowTemplate && (
                    <span className="text-amber-600 font-medium">· {workflowTemplate}</span>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    t('chat.suggestion1'),
                    t('chat.suggestion2'),
                    t('chat.suggestion3'),
                    t('chat.suggestion4'),
                  ].map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => {
                        setInput(suggestion)
                        inputRef.current?.focus()
                      }}
                      className="text-left px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm text-gray-700 hover:border-blue-300 hover:bg-blue-50 transition-all"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto py-6 px-4 space-y-6">
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}
                >
                  {msg.role === 'assistant' && (
                    <div className={`w-8 h-8 ${currentMode.color} rounded-lg flex items-center justify-center shrink-0 mt-0.5`}>
                      <ModeIcon className="w-4 h-4 text-white" />
                    </div>
                  )}
                  <div
                    className={`max-w-[80%] rounded-2xl px-4 py-3 ${msg.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-white border border-gray-200 text-gray-800'
                      }`}
                  >
                    {msg.role === 'assistant' ? (
                      msg.content ? (
                        <MarkdownRenderer content={msg.content} />
                      ) : (
                        <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
                      )
                    ) : (
                      <div className="text-sm leading-relaxed whitespace-pre-wrap">
                        {msg.content}
                      </div>
                    )}
                  </div>
                  {msg.role === 'user' && (
                    <div className="w-8 h-8 bg-gray-700 rounded-lg flex items-center justify-center shrink-0 mt-0.5">
                      <User className="w-4 h-4 text-white" />
                    </div>
                  )}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="border-t border-gray-200 bg-white px-4 py-4 shrink-0">
          <div className="max-w-3xl mx-auto">
            <div className="flex items-end gap-3 bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100 transition-all">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t('chat.inputPlaceholder')}
                rows={1}
                className="flex-1 bg-transparent resize-none outline-none text-gray-800 placeholder-gray-400 text-sm max-h-32"
                style={{ minHeight: '24px' }}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || streaming}
                className="p-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-xl transition-colors shrink-0"
              >
                {streaming ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </button>
            </div>
            <div className="flex items-center justify-between mt-2 px-1">
              <div className="flex items-center gap-1.5 text-xs text-gray-400">
                <ModeIcon className="w-3 h-3" />
                <span>{t(`chat.mode.${agentMode}`)}</span>
                {agentMode === 'workflow' && workflowTemplate && (
                  <span className="text-amber-500">· {workflowTemplate}</span>
                )}
              </div>
              <p className="text-xs text-gray-400">
                {t('chat.inputHint')}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
