import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { formatCost } from '../lib/chat'
import type { Stats } from '../lib/types'
import { Badge, Card, EmptyState, ErrorBanner, PageHeader, Spinner } from '../components/ui'

export function Admin() {
  const [days, setDays] = useState(7)
  const stats = useQuery({
    queryKey: ['stats', days],
    queryFn: () => api<Stats>(`/api/admin/stats?days=${days}`),
    refetchInterval: 15_000,
  })

  return (
    <div>
      <PageHeader
        title="AI usage & cost"
        subtitle="Every LLM call goes through the gateway, which records tokens, cost, latency and cache hits."
        actions={
          <select
            aria-label="Time window"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="rounded-lg border-0 py-1.5 pr-8 pl-2 text-sm ring-1 ring-slate-300"
          >
            <option value={1}>Last 24 hours</option>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
          </select>
        }
      />
      {stats.isLoading ? (
        <div className="grid place-items-center py-16 text-slate-400">
          <Spinner />
        </div>
      ) : stats.isError ? (
        <ErrorBanner message={(stats.error as Error).message} />
      ) : (
        <Dashboard s={stats.data!} />
      )}
    </div>
  )
}

function Dashboard({ s }: { s: Stats }) {
  const { llm } = s
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile label="LLM calls" value={llm.calls.toLocaleString()} />
        <Tile label="Spend" value={formatCost(llm.cost_usd)} hint={`${(llm.input_tokens + llm.output_tokens).toLocaleString()} tokens`} />
        <Tile label="Cache hit rate" value={`${Math.round(llm.cache_hit_rate * 100)}%`} hint="served at zero cost" />
        <Tile label="Latency p50 / p95" value={`${llm.p50_latency_ms} / ${llm.p95_latency_ms} ms`} hint={`${llm.fallback_count} fallbacks`} />
      </div>

      <Card>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-medium text-slate-900">Cost by model and task</h2>
          <div className="flex gap-1.5 text-xs">
            <span className="text-slate-500">Provider chain:</span>
            {s.gateway.providers.map((p, i) => (
              <Badge key={p} tone={i === 0 ? 'indigo' : 'slate'}>
                {i + 1}. {p}
              </Badge>
            ))}
          </div>
        </div>
        {llm.by_model.length === 0 ? (
          <EmptyState title="No AI calls in this window" hint="Ask a question in chat or raise a ticket." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th className="py-2 font-medium">Model</th>
                  <th className="py-2 font-medium">Task</th>
                  <th className="py-2 text-right font-medium">Calls</th>
                  <th className="py-2 text-right font-medium">Avg latency</th>
                  <th className="py-2 text-right font-medium">Cost</th>
                </tr>
              </thead>
              <tbody>
                {llm.by_model.map((m) => (
                  <tr key={`${m.model}-${m.task}`} className="border-b border-slate-100 last:border-0">
                    <td className="py-2">
                      <span className="font-medium text-slate-800">{m.model}</span>{' '}
                      <span className="text-slate-400">({m.provider})</span>
                    </td>
                    <td className="py-2 capitalize">{m.task}</td>
                    <td className="py-2 text-right tabular-nums">{m.calls}</td>
                    <td className="py-2 text-right tabular-nums">{m.avg_latency_ms} ms</td>
                    <td className="py-2 text-right tabular-nums">{formatCost(m.cost_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <h2 className="mb-3 font-medium text-slate-900">Tickets by AI category</h2>
          <Bars data={s.tickets.by_category} />
        </Card>
        <Card>
          <h2 className="mb-3 font-medium text-slate-900">Tickets by status</h2>
          <Bars data={s.tickets.by_status} />
        </Card>
      </div>
      <p className="text-xs text-slate-400">
        {s.documents} documents · {s.users} users · Prometheus metrics at /metrics for Grafana alerting.
      </p>
    </div>
  )
}

function Tile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card className="p-4">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900 tabular-nums">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-slate-400">{hint}</p>}
    </Card>
  )
}

function Bars({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1])
  if (entries.length === 0) return <p className="text-sm text-slate-500">No tickets yet.</p>
  const max = Math.max(...entries.map(([, v]) => v))
  return (
    <ul className="space-y-2">
      {entries.map(([k, v]) => (
        <li key={k} className="grid grid-cols-[110px_1fr_32px] items-center gap-3 text-sm">
          <span className="truncate text-slate-600 capitalize">{k.replace('_', ' ')}</span>
          <div className="h-2.5 rounded-full bg-slate-100">
            <div className="h-2.5 rounded-full bg-indigo-500" style={{ width: `${(v / max) * 100}%` }} />
          </div>
          <span className="text-right text-slate-700 tabular-nums">{v}</span>
        </li>
      ))}
    </ul>
  )
}
