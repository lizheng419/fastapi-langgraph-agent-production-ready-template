import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { useState } from 'react'
import { Copy, Check } from 'lucide-react'

function CodeBlock({ inline, className, children, ...props }) {
  const match = /language-(\w+)/.exec(className || '')
  const lang = match ? match[1] : ''
  const code = String(children).replace(/\n$/, '')
  const [copied, setCopied] = useState(false)

  if (inline || !match) {
    return (
      <code className="px-1.5 py-0.5 bg-gray-100 text-gray-800 rounded text-[13px] font-mono" {...props}>
        {children}
      </code>
    )
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="relative group my-3 rounded-lg overflow-hidden border border-gray-200">
      <div className="flex items-center justify-between bg-gray-100 px-4 py-1.5 text-xs text-gray-500">
        <span className="font-mono">{lang}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 hover:text-gray-700 transition-colors"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-green-600" /> : <Copy className="w-3.5 h-3.5" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <SyntaxHighlighter
        style={oneLight}
        language={lang}
        PreTag="div"
        customStyle={{ margin: 0, borderRadius: 0, fontSize: '13px' }}
        {...props}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  )
}

const components = {
  code: CodeBlock,
  p: ({ children }) => <p className="mb-3 last:mb-0 leading-relaxed">{children}</p>,
  h1: ({ children }) => <h1 className="text-xl font-bold mb-3 mt-4 first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="text-lg font-bold mb-2 mt-3 first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="text-base font-semibold mb-2 mt-3 first:mt-0">{children}</h3>,
  ul: ({ children }) => <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal pl-5 mb-3 space-y-1">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-4 border-blue-300 pl-4 my-3 text-gray-600 italic">{children}</blockquote>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto my-3">
      <table className="min-w-full border border-gray-200 text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-gray-50">{children}</thead>,
  th: ({ children }) => <th className="px-3 py-2 border border-gray-200 font-semibold text-left">{children}</th>,
  td: ({ children }) => <td className="px-3 py-2 border border-gray-200">{children}</td>,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
      {children}
    </a>
  ),
  hr: () => <hr className="my-4 border-gray-200" />,
}

export default function MarkdownRenderer({ content }) {
  if (!content) return null
  return (
    <div className="text-sm">
      <Markdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </Markdown>
    </div>
  )
}
