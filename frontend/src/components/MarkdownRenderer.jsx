import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { useState, useMemo } from 'react'
import { Copy, Check, ChevronDown, Brain } from 'lucide-react'

/**
 * Parse <think>...</think> blocks from LLM output (e.g. Qwen3).
 * Returns an array of segments: { type: 'think' | 'text', content: string }
 * Handles streaming where closing </think> may not yet be present.
 */
function parseThinkBlocks(text) {
  if (!text) return []

  const segments = []
  const regex = /<think>([\s\S]*?)(<\/think>|$)/gi
  let lastIndex = 0

  for (const match of text.matchAll(regex)) {
    if (match.index > lastIndex) {
      const before = text.slice(lastIndex, match.index).trim()
      if (before) segments.push({ type: 'text', content: before })
    }
    const thinkContent = match[1].trim()
    const isClosed = match[2] === '</think>'
    if (thinkContent) {
      segments.push({ type: 'think', content: thinkContent, streaming: !isClosed })
    }
    lastIndex = match.index + match[0].length
  }

  if (lastIndex < text.length) {
    const remaining = text.slice(lastIndex).trim()
    if (remaining) segments.push({ type: 'text', content: remaining })
  }

  if (segments.length === 0 && text.trim()) {
    segments.push({ type: 'text', content: text })
  }

  return segments
}

function ThinkBlock({ content, streaming }) {
  const [expanded, setExpanded] = useState(streaming)

  return (
    <div className="my-2 rounded-lg border border-purple-200 bg-purple-50/50 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-purple-700 hover:bg-purple-100/50 transition-colors"
      >
        <Brain className="w-3.5 h-3.5 shrink-0" />
        <span>{streaming ? 'Thinking...' : 'Thinking Process'}</span>
        <ChevronDown className={`w-3.5 h-3.5 ml-auto transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </button>
      {expanded && (
        <div className="px-3 pb-2.5 text-xs text-purple-900/70 leading-relaxed border-t border-purple-200/60">
          <div className="pt-2 whitespace-pre-wrap">{content}</div>
        </div>
      )}
    </div>
  )
}

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

const markdownComponents = {
  code: CodeBlock,
  p: ({ children }) => <p className="mb-3 last:mb-0 leading-relaxed">{children}</p>,
  h1: ({ children }) => <h1 className="text-xl font-bold mb-3 mt-4 first:mt-0 text-gray-900">{children}</h1>,
  h2: ({ children }) => <h2 className="text-lg font-bold mb-2 mt-3 first:mt-0 text-gray-900">{children}</h2>,
  h3: ({ children }) => <h3 className="text-base font-semibold mb-2 mt-3 first:mt-0 text-gray-900">{children}</h3>,
  h4: ({ children }) => <h4 className="text-sm font-semibold mb-1.5 mt-2.5 first:mt-0 text-gray-800">{children}</h4>,
  ul: ({ children }) => <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal pl-5 mb-3 space-y-1">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-4 border-blue-300 pl-4 my-3 text-gray-600 italic">{children}</blockquote>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto my-3 rounded-lg border border-gray-200">
      <table className="min-w-full text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-gray-50">{children}</thead>,
  th: ({ children }) => <th className="px-3 py-2 border-b border-gray-200 font-semibold text-left text-gray-700">{children}</th>,
  td: ({ children }) => <td className="px-3 py-2 border-b border-gray-100">{children}</td>,
  tr: ({ children }) => <tr className="hover:bg-gray-50/50 transition-colors">{children}</tr>,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 hover:underline">
      {children}
    </a>
  ),
  hr: () => <hr className="my-4 border-gray-200" />,
  strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
  em: ({ children }) => <em className="italic text-gray-700">{children}</em>,
}

function MarkdownBlock({ content }) {
  return (
    <Markdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeRaw]}
      components={markdownComponents}
    >
      {content}
    </Markdown>
  )
}

export default function MarkdownRenderer({ content }) {
  const segments = useMemo(() => parseThinkBlocks(content), [content])

  if (!content) return null

  return (
    <div className="text-sm markdown-body">
      {segments.map((seg, i) =>
        seg.type === 'think' ? (
          <ThinkBlock key={i} content={seg.content} streaming={seg.streaming} />
        ) : (
          <MarkdownBlock key={i} content={seg.content} />
        )
      )}
    </div>
  )
}
