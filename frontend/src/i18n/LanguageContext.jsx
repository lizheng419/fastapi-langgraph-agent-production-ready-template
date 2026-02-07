import { createContext, useContext, useState, useCallback } from 'react'
import zh from './zh.json'
import en from './en.json'

const translations = { zh, en }

const LanguageContext = createContext()

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(() => localStorage.getItem('lang') || 'zh')

  const switchLang = useCallback((newLang) => {
    setLang(newLang)
    localStorage.setItem('lang', newLang)
  }, [])

  const t = useCallback(
    (key, params) => {
      const keys = key.split('.')
      let value = translations[lang]
      for (const k of keys) {
        value = value?.[k]
      }
      if (typeof value !== 'string') return key
      if (params) {
        return value.replace(/\{(\w+)\}/g, (_, name) => params[name] ?? `{${name}}`)
      }
      return value
    },
    [lang]
  )

  return (
    <LanguageContext.Provider value={{ lang, switchLang, t }}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useLanguage() {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLanguage must be used within LanguageProvider')
  return ctx
}
