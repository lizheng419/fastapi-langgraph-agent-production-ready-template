import { useState } from 'react'
import { LogIn, UserPlus, Bot, Globe, KeyRound, ArrowLeft, CheckCircle } from 'lucide-react'
import { register, login, createSession, resetPassword } from '../api'
import { useLanguage } from '../i18n/LanguageContext'

export default function LoginPage({ onAuth }) {
  const { t, lang, switchLang } = useLanguage()
  const [isRegister, setIsRegister] = useState(false)
  const [showResetPassword, setShowResetPassword] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [masterPassword, setMasterPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      if (isRegister) {
        const user = await register(email, password)
        // After registration, create a session
        const session = await createSession(user.token.access_token)
        onAuth({
          userToken: user.token.access_token,
          sessionToken: session.token.access_token,
          sessionId: session.session_id,
          email: user.email,
        })
      } else {
        const tokenData = await login(email, password)
        // Create a session with the user token
        const session = await createSession(tokenData.access_token)
        onAuth({
          userToken: tokenData.access_token,
          sessionToken: session.token.access_token,
          sessionId: session.session_id,
          email,
        })
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleResetPassword = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    setLoading(true)

    try {
      await resetPassword(email, newPassword, masterPassword)
      setSuccess(t('login.resetSuccess'))
      setNewPassword('')
      setMasterPassword('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const switchToReset = () => {
    setShowResetPassword(true)
    setError('')
    setSuccess('')
    setNewPassword('')
    setMasterPassword('')
  }

  const switchToLogin = () => {
    setShowResetPassword(false)
    setError('')
    setSuccess('')
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 flex items-center justify-center px-4">
      {/* Language Switcher */}
      <div className="absolute top-4 right-4">
        <button
          onClick={() => switchLang(lang === 'zh' ? 'en' : 'zh')}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-slate-300 hover:text-white bg-white/10 hover:bg-white/20 rounded-lg transition-all"
        >
          <Globe className="w-4 h-4" />
          {t(`language.${lang === 'zh' ? 'en' : 'zh'}`)}
        </button>
      </div>

      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-600 rounded-2xl mb-4 shadow-lg shadow-blue-600/30">
            <Bot className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white">{t('login.title')}</h1>
          <p className="text-slate-400 mt-2">{t('login.subtitle')}</p>
        </div>

        <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 shadow-2xl border border-white/10">
          {showResetPassword ? (
            <>
              <button
                onClick={switchToLogin}
                className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-white mb-4 transition-all"
              >
                <ArrowLeft className="w-4 h-4" />
                {t('login.backToLogin')}
              </button>
              <h2 className="text-lg font-semibold text-white mb-4">{t('login.resetTitle')}</h2>

              <form onSubmit={handleResetPassword} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">{t('login.email')}</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                    placeholder={t('login.emailPlaceholder')}
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">{t('login.newPassword')}</label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                    placeholder={t('login.newPasswordPlaceholder')}
                    required
                    minLength={6}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">{t('login.masterPassword')}</label>
                  <input
                    type="password"
                    value={masterPassword}
                    onChange={(e) => setMasterPassword(e.target.value)}
                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                    placeholder={t('login.masterPasswordPlaceholder')}
                    required
                  />
                </div>

                {error && (
                  <div className="text-red-400 text-sm bg-red-400/10 rounded-lg px-4 py-2.5">
                    {error}
                  </div>
                )}

                {success && (
                  <div className="text-green-400 text-sm bg-green-400/10 rounded-lg px-4 py-2.5 flex items-center gap-2">
                    <CheckCircle className="w-4 h-4" />
                    {success}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 bg-amber-600 hover:bg-amber-500 disabled:bg-amber-800 disabled:cursor-not-allowed text-white font-medium rounded-lg flex items-center justify-center gap-2 transition-all shadow-lg shadow-amber-600/20"
                >
                  {loading ? (
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <>
                      <KeyRound className="w-4 h-4" /> {t('login.resetButton')}
                    </>
                  )}
                </button>
              </form>
            </>
          ) : (
            <>
              <div className="flex mb-6 bg-white/5 rounded-lg p-1">
                <button
                  onClick={() => setIsRegister(false)}
                  className={`flex-1 py-2.5 text-sm font-medium rounded-md transition-all ${!isRegister ? 'bg-blue-600 text-white shadow-md' : 'text-slate-300 hover:text-white'
                    }`}
                >
                  {t('login.loginTab')}
                </button>
                <button
                  onClick={() => setIsRegister(true)}
                  className={`flex-1 py-2.5 text-sm font-medium rounded-md transition-all ${isRegister ? 'bg-blue-600 text-white shadow-md' : 'text-slate-300 hover:text-white'
                    }`}
                >
                  {t('login.registerTab')}
                </button>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">{t('login.email')}</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                    placeholder={t('login.emailPlaceholder')}
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">{t('login.password')}</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                    placeholder={t('login.passwordPlaceholder')}
                    required
                    minLength={6}
                  />
                </div>

                {error && (
                  <div className="text-red-400 text-sm bg-red-400/10 rounded-lg px-4 py-2.5">
                    {error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 disabled:cursor-not-allowed text-white font-medium rounded-lg flex items-center justify-center gap-2 transition-all shadow-lg shadow-blue-600/20"
                >
                  {loading ? (
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : isRegister ? (
                    <>
                      <UserPlus className="w-4 h-4" /> {t('login.createAccount')}
                    </>
                  ) : (
                    <>
                      <LogIn className="w-4 h-4" /> {t('login.signIn')}
                    </>
                  )}
                </button>

                {!isRegister && (
                  <button
                    type="button"
                    onClick={switchToReset}
                    className="w-full text-sm text-slate-400 hover:text-blue-400 transition-all mt-2"
                  >
                    {t('login.forgotPassword')}
                  </button>
                )}
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
