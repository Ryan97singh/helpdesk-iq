import { describe, expect, it } from 'vitest'
import { applyChatEvent, formatCost } from './chat'
import type { ChatMessage } from './types'

const base: ChatMessage[] = [
  { id: 'q', role: 'user', content: 'hi' },
  { id: 'a', role: 'assistant', content: '', streaming: true },
]

describe('applyChatEvent', () => {
  it('appends streamed tokens only to the target message', () => {
    let m = applyChatEvent(base, 'a', { type: 'token', text: 'Hello ' })
    m = applyChatEvent(m, 'a', { type: 'token', text: 'world' })
    expect(m[1].content).toBe('Hello world')
    expect(m[0]).toBe(base[0])
  })

  it('records sources, usage and finishes streaming', () => {
    const source = { index: 1, document_id: 1, title: 'Leave Policy', score: 0.4, snippet: '...' }
    let m = applyChatEvent(base, 'a', { type: 'sources', sources: [source], pii_redacted: ['EMAIL'] })
    m = applyChatEvent(m, 'a', { type: 'done', usage: null })
    expect(m[1].sources).toEqual([source])
    expect(m[1].piiRedacted).toEqual(['EMAIL'])
    expect(m[1].streaming).toBe(false)
  })

  it('captures errors', () => {
    const m = applyChatEvent(base, 'a', { type: 'error', message: 'boom' })
    expect(m[1]).toMatchObject({ error: 'boom', streaming: false })
  })
})

describe('formatCost', () => {
  it('formats tiny and normal amounts', () => {
    expect(formatCost(0)).toBe('$0')
    expect(formatCost(0.000123)).toBe('$0.00012')
    expect(formatCost(1.5)).toBe('$1.50')
  })
})
