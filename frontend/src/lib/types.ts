export type Role = 'employee' | 'agent' | 'admin'

export interface User {
  id: number
  email: string
  name: string
  role: Role
  auth_provider: string
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  user: User
}

export interface DocumentItem {
  id: number
  title: string
  filename: string
  status: 'pending' | 'ready' | 'failed'
  chunk_count: number
  created_at: string
}

export type TicketStatus = 'open' | 'in_progress' | 'resolved'

export interface Ticket {
  id: number
  title: string
  description: string
  status: TicketStatus
  category: string | null
  priority: 'low' | 'medium' | 'high' | 'urgent' | null
  suggested_reply: string | null
  triage_status: 'pending' | 'done' | 'failed'
  created_by: number
  created_at: string
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export interface Source {
  index: number
  document_id: number
  title: string
  score: number
  snippet: string
}

export interface Usage {
  provider: string
  model: string
  input_tokens: number
  output_tokens: number
  cost_usd: number
  latency_ms: number
  cache_hit: boolean
  fallback_used: boolean
}

export type ChatEvent =
  | { type: 'sources'; sources: Source[]; pii_redacted: string[] }
  | { type: 'token'; text: string }
  | { type: 'done'; usage: Usage | null }
  | { type: 'error'; message: string }

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  usage?: Usage | null
  error?: string
  piiRedacted?: string[]
  streaming?: boolean
}

export interface Stats {
  window_days: number
  llm: {
    calls: number
    input_tokens: number
    output_tokens: number
    cost_usd: number
    cache_hit_rate: number
    fallback_count: number
    p50_latency_ms: number
    p95_latency_ms: number
    by_model: { provider: string; model: string; task: string; calls: number; cost_usd: number; avg_latency_ms: number }[]
    daily: { day: string; calls: number; cost_usd: number }[]
  }
  tickets: { by_category: Record<string, number>; by_status: Record<string, number> }
  documents: number
  users: number
  gateway: { providers: string[]; configured_primary: string; daily_budget_usd: number; spent_today_usd: number }
}
