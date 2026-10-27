import type { ChatEvent, ChatMessage } from './types'

/** Pure reducer: fold one SSE event into the assistant message it belongs to. */
export function applyChatEvent(messages: ChatMessage[], id: string, event: ChatEvent): ChatMessage[] {
  return messages.map((m) => {
    if (m.id !== id) return m
    switch (event.type) {
      case 'sources':
        return { ...m, sources: event.sources, piiRedacted: event.pii_redacted }
      case 'token':
        return { ...m, content: m.content + event.text }
      case 'done':
        return { ...m, usage: event.usage, streaming: false }
      case 'error':
        return { ...m, error: event.message, streaming: false }
    }
  })
}

export function formatCost(usd: number): string {
  if (usd === 0) return '$0'
  if (usd < 0.01) return `$${usd.toFixed(5)}`
  return `$${usd.toFixed(2)}`
}
