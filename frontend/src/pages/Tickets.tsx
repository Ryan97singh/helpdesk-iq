import { useState, type FormEvent } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError, patch, post } from '../lib/api'
import type { Page, Ticket, TicketStatus } from '../lib/types'
import { useAuth } from '../store/auth'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBanner,
  PageHeader,
  Spinner,
} from '../components/ui'
import { priorityTone, statusLabel, statusTone } from '../lib/labels'

const PAGE_SIZE = 10
const STATUSES: TicketStatus[] = ['open', 'in_progress', 'resolved']

export function Tickets() {
  const user = useAuth((s) => s.user)!
  const isStaff = user.role !== 'employee'
  const [status, setStatus] = useState<TicketStatus | ''>('')
  const [page, setPage] = useState(1)
  const [showForm, setShowForm] = useState(false)

  const query = useQuery({
    queryKey: ['tickets', status, page],
    queryFn: () =>
      api<Page<Ticket>>(`/api/tickets?page=${page}&size=${PAGE_SIZE}${status ? `&status=${status}` : ''}`),
    placeholderData: keepPreviousData,
    // Triage runs asynchronously in the worker: poll until every visible ticket is triaged.
    refetchInterval: (q) => (q.state.data?.items.some((t) => t.triage_status === 'pending') ? 1500 : false),
  })
  const pages = Math.max(1, Math.ceil((query.data?.total ?? 0) / PAGE_SIZE))

  return (
    <div>
      <PageHeader
        title={isStaff ? 'All tickets' : 'My tickets'}
        subtitle="New tickets are categorised and prioritised by AI within seconds."
        actions={!showForm && <Button onClick={() => setShowForm(true)}>New ticket</Button>}
      />

      {showForm && <NewTicketForm onDone={() => setShowForm(false)} />}

      <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Filter by status">
        {(['', ...STATUSES] as const).map((s) => (
          <button
            key={s || 'all'}
            onClick={() => {
              setStatus(s)
              setPage(1)
            }}
            aria-pressed={status === s}
            className={`rounded-full px-3 py-1 text-sm font-medium ${
              status === s ? 'bg-slate-900 text-white' : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50'
            }`}
          >
            {s ? statusLabel[s] : 'All'}
          </button>
        ))}
      </div>

      {query.isLoading ? (
        <div className="grid place-items-center py-16 text-slate-400">
          <Spinner />
        </div>
      ) : query.isError ? (
        <ErrorBanner message={(query.error as Error).message} />
      ) : query.data!.items.length === 0 ? (
        <EmptyState
          title={status ? `No ${statusLabel[status].toLowerCase()} tickets` : 'No tickets yet'}
          hint="Can't find an answer in chat? Raise a ticket and the helpdesk team will pick it up."
        />
      ) : (
        <div className="space-y-3">
          {query.data!.items.map((t) => (
            <TicketCard key={t.id} ticket={t} isStaff={isStaff} />
          ))}
          {pages > 1 && (
            <div className="flex items-center justify-between pt-2 text-sm text-slate-600">
              <span>
                Page {page} of {pages} · {query.data!.total} tickets
              </span>
              <div className="flex gap-2">
                <Button variant="secondary" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
                  Previous
                </Button>
                <Button variant="secondary" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>
                  Next
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function NewTicketForm({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const create = useMutation({
    mutationFn: () => post<Ticket>('/api/tickets', { title, description }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tickets'] })
      onDone()
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    create.mutate()
  }
  return (
    <Card className="mb-6">
      <form onSubmit={submit} className="space-y-3">
        <h2 className="font-medium text-slate-900">Raise a ticket</h2>
        {create.isError && <ErrorBanner message={(create.error as ApiError).message} />}
        <div>
          <label htmlFor="ticket-title" className="mb-1 block text-sm font-medium text-slate-700">
            Title
          </label>
          <input
            id="ticket-title"
            required
            minLength={3}
            maxLength={200}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. VPN not connecting"
            className="w-full rounded-lg border-0 px-3 py-2 text-sm ring-1 ring-slate-300 focus:ring-2 focus:ring-indigo-600 focus:outline-none"
          />
        </div>
        <div>
          <label htmlFor="ticket-description" className="mb-1 block text-sm font-medium text-slate-700">
            Description
          </label>
          <textarea
            id="ticket-description"
            required
            minLength={5}
            rows={4}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What happened, and how is it affecting your work?"
            className="w-full rounded-lg border-0 px-3 py-2 text-sm ring-1 ring-slate-300 focus:ring-2 focus:ring-indigo-600 focus:outline-none"
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onDone}>
            Cancel
          </Button>
          <Button type="submit" loading={create.isPending}>
            Submit ticket
          </Button>
        </div>
      </form>
    </Card>
  )
}

function TicketCard({ ticket: t, isStaff }: { ticket: Ticket; isStaff: boolean }) {
  const queryClient = useQueryClient()
  const update = useMutation({
    mutationFn: (status: TicketStatus) => patch<Ticket>(`/api/tickets/${t.id}`, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tickets'] }),
  })
  const retriage = useMutation({
    mutationFn: () => post<Ticket>(`/api/tickets/${t.id}/retriage`, {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tickets'] }),
  })

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-xs text-slate-400">
            #{t.id} · {new Date(t.created_at).toLocaleString()}
          </p>
          <h3 className="mt-0.5 font-medium text-slate-900">{t.title}</h3>
          <p className="mt-1 line-clamp-2 text-sm text-slate-600">{t.description}</p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {t.triage_status === 'pending' ? (
            <Badge>
              <Spinner className="mr-1 h-3 w-3" /> AI triaging
            </Badge>
          ) : t.triage_status === 'failed' ? (
            <Badge tone="red">Triage failed</Badge>
          ) : (
            <>
              <Badge tone="indigo">{t.category}</Badge>
              {t.priority && <Badge tone={priorityTone[t.priority]}>{t.priority}</Badge>}
            </>
          )}
          <Badge tone={statusTone[t.status]}>{statusLabel[t.status]}</Badge>
        </div>
      </div>

      {isStaff && t.suggested_reply && (
        <div className="mt-4 rounded-lg bg-indigo-50/60 p-3 text-sm">
          <p className="text-xs font-medium tracking-wide text-indigo-700 uppercase">AI-suggested reply</p>
          <p className="mt-1 text-slate-700">{t.suggested_reply}</p>
        </div>
      )}

      {isStaff && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <label htmlFor={`status-${t.id}`} className="text-sm text-slate-600">
            Status
          </label>
          <select
            id={`status-${t.id}`}
            value={t.status}
            disabled={update.isPending}
            onChange={(e) => update.mutate(e.target.value as TicketStatus)}
            className="rounded-lg border-0 py-1.5 pr-8 pl-2 text-sm ring-1 ring-slate-300 focus:ring-2 focus:ring-indigo-600"
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {statusLabel[s]}
              </option>
            ))}
          </select>
          <Button variant="ghost" onClick={() => retriage.mutate()} loading={retriage.isPending}>
            Re-run AI triage
          </Button>
          {(update.isError || retriage.isError) && (
            <span className="text-sm text-red-600">{((update.error ?? retriage.error) as Error).message}</span>
          )}
        </div>
      )}
    </Card>
  )
}
