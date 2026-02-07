import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  ShieldCheck,
  ShieldX,
  Clock,
  CheckCircle2,
  XCircle,
  RefreshCw,
  MessageSquare,
  WifiOff,
} from 'lucide-react'
import { getPendingApprovals, approveRequest, rejectRequest, isNetworkError } from '../api'
import { useLanguage } from '../i18n/LanguageContext'

export default function ApprovalsPage({ auth, onLogout }) {
  const { t } = useLanguage()
  const [approvals, setApprovals] = useState([])
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(null)
  const [comment, setComment] = useState({})
  const [showComment, setShowComment] = useState(null)
  const [connectionError, setConnectionError] = useState(false)
  const navigate = useNavigate()

  const fetchApprovals = async () => {
    setLoading(true)
    try {
      const data = await getPendingApprovals(auth.sessionToken)
      setApprovals(data.requests || [])
      setConnectionError(false)
    } catch (err) {
      if (isNetworkError(err) || err.message?.includes('unreachable')) {
        setConnectionError(true)
      } else {
        setApprovals([])
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchApprovals()
    const interval = setInterval(fetchApprovals, 10000)
    return () => clearInterval(interval)
  }, [])

  const handleApprove = async (id) => {
    setActionLoading(id)
    try {
      await approveRequest(auth.sessionToken, id, comment[id] || null)
      await fetchApprovals()
    } catch (err) {
      if (isNetworkError(err) || err.message?.includes('unreachable')) setConnectionError(true)
    }
    setActionLoading(null)
  }

  const handleReject = async (id) => {
    setActionLoading(id)
    try {
      await rejectRequest(auth.sessionToken, id, comment[id] || null)
      await fetchApprovals()
    } catch (err) {
      if (isNetworkError(err) || err.message?.includes('unreachable')) setConnectionError(true)
    }
    setActionLoading(null)
  }

  const formatTime = (dateStr) => {
    try {
      return new Date(dateStr).toLocaleString()
    } catch {
      return dateStr
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/')}
              className="p-2 text-gray-400 hover:text-gray-700 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-blue-600" />
                {t('approvals.title')}
              </h1>
              <p className="text-sm text-gray-500">{t('approvals.subtitle')}</p>
            </div>
          </div>
          <button
            onClick={fetchApprovals}
            disabled={loading}
            className="px-3 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg flex items-center gap-1.5 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> {t('approvals.refresh')}
          </button>
        </div>
      </header>

      {/* Connection Error Banner */}
      {connectionError && (
        <div className="bg-amber-50 border-b border-amber-200 px-6 py-2.5 flex items-center justify-between">
          <div className="flex items-center gap-2 text-amber-700 text-sm">
            <WifiOff className="w-4 h-4" />
            <span>{t('chat.connectionError') || 'Cannot reach server. Retrying automatically...'}</span>
          </div>
        </div>
      )}

      {/* Content */}
      <main className="max-w-4xl mx-auto py-8 px-4">
        {loading && approvals.length === 0 ? (
          <div className="text-center py-20">
            <RefreshCw className="w-8 h-8 text-gray-400 animate-spin mx-auto mb-4" />
            <p className="text-gray-500">{t('approvals.loading')}</p>
          </div>
        ) : approvals.length === 0 ? (
          <div className="text-center py-20">
            <div className="w-16 h-16 bg-green-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="w-8 h-8 text-green-600" />
            </div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">{t('approvals.allClear')}</h2>
            <p className="text-gray-500 mb-6">{t('approvals.noApprovals')}</p>
            <button
              onClick={() => navigate('/')}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-500 transition-colors text-sm"
            >
              {t('approvals.backToChat')}
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm text-gray-500">
                {t('approvals.pendingCount', { count: approvals.length })}
              </p>
            </div>

            {approvals.map((req) => (
              <div
                key={req.id}
                className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow"
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 bg-amber-100 text-amber-700 text-xs font-medium rounded-full">
                        <Clock className="w-3 h-3" /> {t('approvals.pending')}
                      </span>
                      <span className="text-xs text-gray-400 font-mono">{req.id.slice(0, 8)}...</span>
                    </div>
                    <h3 className="text-base font-medium text-gray-900 mt-2">
                      {req.action_description}
                    </h3>
                    <p className="text-sm text-gray-500 mt-1">
                      {t('approvals.type')}: <span className="font-medium">{req.action_type}</span>
                    </p>
                  </div>
                </div>

                {/* Action data */}
                {req.action_data && Object.keys(req.action_data).length > 0 && (
                  <div className="bg-gray-50 rounded-lg p-3 mb-4">
                    <p className="text-xs text-gray-500 mb-1 font-medium">{t('approvals.actionDetails')}</p>
                    <pre className="text-xs text-gray-700 overflow-x-auto">
                      {JSON.stringify(req.action_data, null, 2)}
                    </pre>
                  </div>
                )}

                <div className="flex items-center justify-between text-xs text-gray-400 mb-4">
                  <span>{t('approvals.created')}: {formatTime(req.created_at)}</span>
                  <span>{t('approvals.expires')}: {formatTime(req.expires_at)}</span>
                </div>

                {/* Comment toggle */}
                <div className="mb-3">
                  <button
                    onClick={() => setShowComment(showComment === req.id ? null : req.id)}
                    className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1"
                  >
                    <MessageSquare className="w-3 h-3" />
                    {showComment === req.id ? t('approvals.hideComment') : t('approvals.addComment')}
                  </button>
                  {showComment === req.id && (
                    <textarea
                      value={comment[req.id] || ''}
                      onChange={(e) => setComment({ ...comment, [req.id]: e.target.value })}
                      placeholder={t('approvals.commentPlaceholder')}
                      className="mt-2 w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-200 resize-none"
                      rows={2}
                    />
                  )}
                </div>

                {/* Action buttons */}
                <div className="flex gap-3">
                  <button
                    onClick={() => handleApprove(req.id)}
                    disabled={actionLoading === req.id}
                    className="flex-1 py-2.5 bg-green-600 hover:bg-green-500 disabled:bg-green-300 text-white text-sm font-medium rounded-lg flex items-center justify-center gap-2 transition-colors"
                  >
                    {actionLoading === req.id ? (
                      <RefreshCw className="w-4 h-4 animate-spin" />
                    ) : (
                      <CheckCircle2 className="w-4 h-4" />
                    )}
                    {t('approvals.approve')}
                  </button>
                  <button
                    onClick={() => handleReject(req.id)}
                    disabled={actionLoading === req.id}
                    className="flex-1 py-2.5 bg-red-600 hover:bg-red-500 disabled:bg-red-300 text-white text-sm font-medium rounded-lg flex items-center justify-center gap-2 transition-colors"
                  >
                    {actionLoading === req.id ? (
                      <RefreshCw className="w-4 h-4 animate-spin" />
                    ) : (
                      <XCircle className="w-4 h-4" />
                    )}
                    {t('approvals.reject')}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
