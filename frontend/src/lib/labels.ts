import type { Tone } from '../components/ui'

export const priorityTone: Record<string, Tone> = { urgent: 'red', high: 'amber', medium: 'indigo', low: 'slate' }
export const statusTone: Record<string, Tone> = { open: 'amber', in_progress: 'indigo', resolved: 'green' }
export const statusLabel: Record<string, string> = { open: 'Open', in_progress: 'In progress', resolved: 'Resolved' }
