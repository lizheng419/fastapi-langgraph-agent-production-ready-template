import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload, FileText, Trash2, ArrowLeft, Loader2, AlertCircle, CheckCircle2, FileUp, File, X, Eye } from 'lucide-react'
import { uploadDocument, getDocuments, deleteDocument, getDocumentChunks } from '../api'
import { useLanguage } from '../i18n/LanguageContext'

const SUPPORTED_TYPES = {
  'application/pdf': '.pdf',
  'text/plain': '.txt',
  'text/markdown': '.md',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
}
const ACCEPT_STRING = '.pdf,.txt,.md,.docx'
const MAX_SIZE_MB = 50

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(iso) {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

export default function KnowledgePage({ auth, onLogout }) {
  const { t } = useLanguage()
  const navigate = useNavigate()
  const fileInputRef = useRef(null)

  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const [deletingId, setDeletingId] = useState(null)
  const [chunksModal, setChunksModal] = useState(null)
  const [chunksLoading, setChunksLoading] = useState(false)

  const token = auth?.userToken || auth?.sessionToken

  const loadDocuments = async () => {
    try {
      setLoading(true)
      const data = await getDocuments(token)
      setDocuments(data.documents || [])
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDocuments()
  }, [token])

  const handleUpload = async (file) => {
    if (!file) return

    const ext = '.' + file.name.split('.').pop().toLowerCase()
    if (!['.pdf', '.txt', '.md', '.docx'].includes(ext)) {
      setError(t('knowledge.unsupportedType') || `Unsupported file type: ${ext}`)
      return
    }

    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(t('knowledge.fileTooLarge') || `File too large. Max: ${MAX_SIZE_MB}MB`)
      return
    }

    setUploading(true)
    setError('')
    setSuccess('')
    setUploadProgress(file.name)

    try {
      const result = await uploadDocument(token, file)
      setSuccess(
        `${t('knowledge.uploadSuccess') || 'Uploaded'}: ${result.filename} (${result.chunk_count} ${t('knowledge.chunks') || 'chunks'})`
      )
      await loadDocuments()
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
      setUploadProgress(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleDelete = async (docId) => {
    if (!confirm(t('knowledge.confirmDelete') || 'Are you sure you want to delete this document?')) return
    setDeletingId(docId)
    try {
      await deleteDocument(token, docId)
      setDocuments((prev) => prev.filter((d) => d.doc_id !== docId))
      setSuccess(t('knowledge.deleteSuccess') || 'Document deleted')
    } catch (err) {
      setError(err.message)
    } finally {
      setDeletingId(null)
    }
  }

  const handleViewChunks = async (doc) => {
    setChunksLoading(true)
    setError('')
    try {
      const data = await getDocumentChunks(token, doc.doc_id, doc.provider || '')
      setChunksModal({ filename: doc.filename, chunks: data.chunks || [], total: data.total || 0 })
    } catch (err) {
      setError(err.message)
    } finally {
      setChunksLoading(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer?.files?.[0]
    if (file) handleUpload(file)
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    setDragOver(true)
  }

  const handleDragLeave = () => setDragOver(false)

  const fileTypeIcon = (filename) => {
    const ext = filename?.split('.').pop()?.toLowerCase()
    const colors = { pdf: 'text-red-500', docx: 'text-blue-500', txt: 'text-gray-500', md: 'text-green-500' }
    return colors[ext] || 'text-gray-400'
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/')}
              className="p-2 text-gray-400 hover:text-gray-700 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="w-9 h-9 bg-emerald-600 rounded-lg flex items-center justify-center">
              <FileText className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-gray-900">{t('knowledge.title') || 'Knowledge Base'}</h1>
              <p className="text-xs text-gray-500">{t('knowledge.subtitle') || 'Upload documents for AI retrieval'}</p>
            </div>
          </div>
          <div className="text-xs text-gray-400">
            {documents.length} {t('knowledge.documentsCount') || 'document(s)'}
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Notifications */}
        {error && (
          <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span className="flex-1">{error}</span>
            <button onClick={() => setError('')} className="p-0.5 hover:bg-red-100 rounded">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
        {success && (
          <div className="flex items-center gap-2 bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-xl text-sm">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span className="flex-1">{success}</span>
            <button onClick={() => setSuccess('')} className="p-0.5 hover:bg-green-100 rounded">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Upload Area */}
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          className={`border-2 border-dashed rounded-2xl p-8 text-center transition-all ${dragOver
            ? 'border-emerald-400 bg-emerald-50'
            : 'border-gray-300 bg-white hover:border-gray-400'
            }`}
        >
          {uploading ? (
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="w-10 h-10 text-emerald-500 animate-spin" />
              <p className="text-sm text-gray-600">
                {t('knowledge.uploading') || 'Processing'}: <span className="font-medium">{uploadProgress}</span>
              </p>
              <p className="text-xs text-gray-400">{t('knowledge.uploadingHint') || 'Parsing, chunking, and embedding...'}</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <div className="w-14 h-14 bg-gray-100 rounded-2xl flex items-center justify-center">
                <FileUp className="w-7 h-7 text-gray-400" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-700">
                  {t('knowledge.dropHere') || 'Drag & drop a file here, or'}
                </p>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="text-sm text-emerald-600 hover:text-emerald-700 font-medium underline underline-offset-2"
                >
                  {t('knowledge.browse') || 'browse files'}
                </button>
              </div>
              <p className="text-xs text-gray-400">
                {t('knowledge.supportedFormats') || 'Supported: PDF, TXT, Markdown, DOCX'} · {t('knowledge.maxSize') || `Max ${MAX_SIZE_MB}MB`}
              </p>
            </div>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPT_STRING}
            className="hidden"
            onChange={(e) => handleUpload(e.target.files?.[0])}
          />
        </div>

        {/* Document List */}
        <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-900">{t('knowledge.documentList') || 'Documents'}</h2>
            <button
              onClick={loadDocuments}
              disabled={loading}
              className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100 transition-colors"
            >
              {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : t('knowledge.refresh') || 'Refresh'}
            </button>
          </div>

          {loading && documents.length === 0 ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
            </div>
          ) : documents.length === 0 ? (
            <div className="flex flex-col items-center py-12 text-gray-400">
              <File className="w-10 h-10 mb-3" />
              <p className="text-sm">{t('knowledge.noDocuments') || 'No documents yet'}</p>
              <p className="text-xs mt-1">{t('knowledge.noDocumentsHint') || 'Upload a document to get started'}</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {documents.map((doc) => (
                <div
                  key={doc.doc_id}
                  className="px-5 py-3.5 flex items-center gap-4 hover:bg-gray-50 transition-colors group"
                >
                  <div className={`shrink-0 ${fileTypeIcon(doc.filename)}`}>
                    <FileText className="w-5 h-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{doc.filename}</p>
                    <div className="flex items-center gap-3 mt-0.5">
                      <span className="text-xs text-gray-400">
                        {doc.chunk_count} {t('knowledge.chunks') || 'chunks'}
                      </span>
                      {doc.provider && (
                        <span className="text-xs text-indigo-500 bg-indigo-50 px-1.5 py-0.5 rounded">
                          {doc.provider}
                        </span>
                      )}
                      <span className="text-xs text-gray-400">{formatDate(doc.created_at)}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleViewChunks(doc)}
                    disabled={chunksLoading}
                    className="p-2 text-gray-400 hover:text-emerald-500 rounded-lg hover:bg-emerald-50 transition-all opacity-0 group-hover:opacity-100"
                    title={t('knowledge.viewChunks') || 'View Chunks'}
                  >
                    <Eye className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(doc.doc_id)}
                    disabled={deletingId === doc.doc_id}
                    className="p-2 text-gray-400 hover:text-red-500 rounded-lg hover:bg-red-50 transition-all opacity-0 group-hover:opacity-100"
                    title={t('knowledge.delete') || 'Delete'}
                  >
                    {deletingId === doc.doc_id ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Trash2 className="w-4 h-4" />
                    )}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Chunks Modal */}
        {chunksModal && (
          <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setChunksModal(null)}>
            <div
              className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[85vh] flex flex-col"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between shrink-0">
                <div>
                  <h3 className="text-base font-semibold text-gray-900">{chunksModal.filename}</h3>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {chunksModal.total} {t('knowledge.chunks') || 'chunks'}
                  </p>
                </div>
                <button
                  onClick={() => setChunksModal(null)}
                  className="p-2 text-gray-400 hover:text-gray-700 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="flex-1 overflow-y-auto p-6 space-y-4">
                {chunksModal.chunks.map((chunk, idx) => (
                  <div key={idx} className="border border-gray-200 rounded-xl overflow-hidden">
                    <div className="bg-gray-50 px-4 py-2 border-b border-gray-200 flex items-center justify-between">
                      <span className="text-xs font-medium text-gray-600">
                        Chunk #{chunk.chunk_index}
                      </span>
                      <span className="text-xs text-gray-400">
                        {chunk.content?.length || 0} {t('knowledge.characters') || 'chars'}
                      </span>
                    </div>
                    <pre className="px-4 py-3 text-sm text-gray-700 whitespace-pre-wrap break-words font-mono leading-relaxed max-h-60 overflow-y-auto bg-white">
                      {chunk.content}
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Info Card */}
        <div className="bg-blue-50 border border-blue-200 rounded-2xl px-5 py-4">
          <h3 className="text-sm font-medium text-blue-800 mb-1">{t('knowledge.howItWorks') || 'How it works'}</h3>
          <p className="text-xs text-blue-600 leading-relaxed">
            {t('knowledge.howItWorksDesc') ||
              'Uploaded documents are parsed, split into chunks, converted to vector embeddings, and stored in the Qdrant vector database. When chatting with the AI, it can automatically retrieve relevant content from your knowledge base using the retrieve_knowledge tool.'}
          </p>
        </div>
      </main>
    </div>
  )
}
