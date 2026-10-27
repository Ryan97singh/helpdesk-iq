import { useRef, useState, type ChangeEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from '../lib/api'
import type { DocumentItem } from '../lib/types'
import { useAuth } from '../store/auth'
import { Badge, Button, Card, EmptyState, ErrorBanner, PageHeader, Spinner } from '../components/ui'

const statusBadge = {
  pending: <Badge tone="amber">Indexing...</Badge>,
  ready: <Badge tone="green">Ready</Badge>,
  failed: <Badge tone="red">Failed</Badge>,
}

export function Documents() {
  const queryClient = useQueryClient()
  const isAdmin = useAuth((s) => s.user?.role === 'admin')
  const fileRef = useRef<HTMLInputElement>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const docs = useQuery({
    queryKey: ['documents'],
    queryFn: () => api<DocumentItem[]>('/api/documents'),
    refetchInterval: (q) => (q.state.data?.some((d) => d.status === 'pending') ? 1500 : false),
  })

  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return api<DocumentItem>('/api/documents', { method: 'POST', body: form })
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['documents'] }),
    onError: (err) => setUploadError(err instanceof ApiError ? err.message : 'Upload failed'),
  })

  const remove = useMutation({
    mutationFn: (id: number) => api(`/api/documents/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['documents'] }),
  })

  const onFile = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setUploadError(null)
    if (file.size > 10 * 1024 * 1024) {
      setUploadError('File exceeds 10 MB')
      return
    }
    upload.mutate(file)
  }

  return (
    <div>
      <PageHeader
        title="Knowledge base"
        subtitle="Policies the assistant answers from. Uploads are chunked and embedded in the background."
        actions={
          <>
            <input ref={fileRef} type="file" accept=".pdf,.md,.txt" className="hidden" onChange={onFile} aria-label="Upload document" />
            <Button onClick={() => fileRef.current?.click()} loading={upload.isPending}>
              Upload document
            </Button>
          </>
        }
      />
      {uploadError && (
        <div className="mb-4">
          <ErrorBanner message={uploadError} />
        </div>
      )}

      {docs.isLoading ? (
        <div className="grid place-items-center py-16 text-slate-400">
          <Spinner />
        </div>
      ) : docs.isError ? (
        <ErrorBanner message={(docs.error as Error).message} />
      ) : docs.data!.length === 0 ? (
        <EmptyState title="No documents yet" hint="Upload a PDF, Markdown or text policy to get started." />
      ) : (
        <Card className="p-0">
          <ul className="divide-y divide-slate-100">
            {docs.data!.map((d) => (
              <li key={d.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
                <div className="min-w-0">
                  <p className="truncate font-medium text-slate-900">{d.title}</p>
                  <p className="text-xs text-slate-500">
                    {d.filename} · {d.status === 'ready' ? `${d.chunk_count} chunk${d.chunk_count === 1 ? '' : 's'} · ` : ''}
                    {new Date(d.created_at).toLocaleDateString()}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  {statusBadge[d.status]}
                  {isAdmin && (
                    <Button variant="danger" onClick={() => remove.mutate(d.id)} disabled={remove.isPending}>
                      Delete
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
