import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api, ApiError, streamChat } from '../lib/api'
import { applyChatEvent, formatCost } from '../lib/chat'
import type { ChatMessage } from '../lib/types'
import { Badge, Button, Spinner } from '../components/ui'

const SUGGESTIONS = [
  'How many sick leave days do I get?',
  'My account is locked, what should I do?',
  'When will my expense claim be paid?',
  'Which days do I need to be in the office?',
]

interface StoredMessage {
  role: 'user' | 'assistant'
  content: string
  meta: { sources?: ChatMessage['sources'] }
}

export function Chat() {
  const queryClient = useQueryClient()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const history = useQuery({ queryKey: ['chat-history'], queryFn: () => api<StoredMessage[]>('/api/chat/history') })

  useEffect(() => {
    if (history.data && messages.length === 0) {
      setMessages(
        history.data.map((m, i) => ({ id: `h${i}`, role: m.role, content: m.content, sources: m.meta?.sources })),
      )
    }
    // only hydrate once from server history
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [history.data])

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' })
  }, [messages])

  const send = async (text: string) => {
    const question = text.trim()
    if (!question || busy) return
    const id = crypto.randomUUID()
    setMessages((m) => [
      ...m,
      { id: `${id}-q`, role: 'user', content: question },
      { id, role: 'assistant', content: '', streaming: true },
    ])
    setInput('')
    setBusy(true)
    const controller = new AbortController()
    abortRef.current = controller
    try {
      await streamChat(question, (event) => setMessages((m) => applyChatEvent(m, id, event)), controller.signal)
    } catch (err) {
      const aborted = err instanceof DOMException && err.name === 'AbortError'
      const message = aborted ? 'Stopped.' : err instanceof ApiError ? err.message : 'Connection lost. Please retry.'
      setMessages((m) => applyChatEvent(m, id, { type: 'error', message }))
    } finally {
      setBusy(false)
      abortRef.current = null
      queryClient.invalidateQueries({ queryKey: ['chat-history'] })
    }
  }

  const clear = async () => {
    await api('/api/chat/history', { method: 'DELETE' })
    setMessages([])
    queryClient.setQueryData(['chat-history'], [])
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    send(input)
  }
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  return (
    <div className="flex h-[calc(100dvh-7rem)] flex-col md:h-[calc(100dvh-4rem)]">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Ask HelpdeskIQ</h1>
          <p className="text-sm text-slate-500">Answers come from company policies, with sources.</p>
        </div>
        {messages.length > 0 && (
          <Button variant="ghost" onClick={clear} disabled={busy}>
            Clear chat
          </Button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto rounded-xl bg-white p-4 ring-1 ring-slate-200" aria-live="polite">
        {history.isLoading ? (
          <div className="grid h-full place-items-center text-slate-400">
            <Spinner />
          </div>
        ) : messages.length === 0 ? (
          <div className="mx-auto flex h-full max-w-lg flex-col items-center justify-center text-center">
            <p className="font-medium text-slate-800">How can I help today?</p>
            <p className="mt-1 text-sm text-slate-500">Try one of these:</p>
            <div className="mt-4 grid w-full gap-2 sm:grid-cols-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-lg px-3 py-2 text-left text-sm text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-5">
            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <form onSubmit={onSubmit} className="mt-3 flex items-end gap-2">
        <label htmlFor="chat-input" className="sr-only">
          Your question
        </label>
        <textarea
          id="chat-input"
          rows={1}
          value={input}
          maxLength={2000}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask about leave, IT, expenses..."
          className="max-h-40 min-h-[42px] flex-1 resize-none rounded-lg border-0 px-3 py-2.5 text-sm ring-1 ring-slate-300 focus:ring-2 focus:ring-indigo-600 focus:outline-none"
        />
        {busy ? (
          <Button type="button" variant="secondary" onClick={() => abortRef.current?.abort()}>
            Stop
          </Button>
        ) : (
          <Button type="submit" disabled={!input.trim()}>
            Send
          </Button>
        )}
      </form>
    </div>
  )
}

function MessageBubble({ message: m }: { message: ChatMessage }) {
  if (m.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-indigo-600 px-4 py-2.5 text-sm whitespace-pre-wrap text-white">
          {m.content}
        </div>
      </div>
    )
  }
  return (
    <div className="max-w-[90%]">
      {(m.content || m.streaming) && (
        <div className="rounded-2xl rounded-bl-sm bg-slate-100 px-4 py-2.5 text-sm whitespace-pre-wrap text-slate-800">
          {m.content || <span className="text-slate-400">Searching policies...</span>}
          {m.streaming && m.content && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-slate-400 align-middle" />}
        </div>
      )}
      {m.error && <p className="mt-1.5 text-sm text-red-600">{m.error}</p>}
      {m.error && m.error !== 'Stopped.' && (
        <Link to="/tickets" className="mt-1 inline-block text-sm font-medium text-indigo-600 hover:underline">
          Raise a ticket instead
        </Link>
      )}
      {m.piiRedacted && m.piiRedacted.length > 0 && (
        <p className="mt-1.5 text-xs text-amber-700">
          Personal data ({m.piiRedacted.join(', ').toLowerCase()}) was redacted before reaching the AI model.
        </p>
      )}
      {m.sources && m.sources.length > 0 && (
        <details className="mt-2 text-sm">
          <summary className="cursor-pointer text-slate-500 hover:text-slate-700">
            {m.sources.length} source{m.sources.length > 1 ? 's' : ''}:{' '}
            {[...new Set(m.sources.map((s) => s.title))].join(', ')}
          </summary>
          <ul className="mt-2 space-y-2">
            {m.sources.map((s) => (
              <li key={s.index} className="rounded-lg bg-white p-3 ring-1 ring-slate-200">
                <p className="font-medium text-slate-700">
                  [{s.index}] {s.title} <span className="font-normal text-slate-400">· relevance {s.score}</span>
                </p>
                <p className="mt-1 text-slate-500">{s.snippet}...</p>
              </li>
            ))}
          </ul>
        </details>
      )}
      {m.usage && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
          <Badge tone="indigo">{m.usage.model}</Badge>
          {m.usage.cache_hit && <Badge tone="green">cache hit</Badge>}
          {m.usage.fallback_used && <Badge tone="amber">fallback: {m.usage.provider}</Badge>}
          <span>
            {m.usage.input_tokens + m.usage.output_tokens} tokens · {formatCost(m.usage.cost_usd)} · {m.usage.latency_ms} ms
          </span>
        </div>
      )}
    </div>
  )
}
