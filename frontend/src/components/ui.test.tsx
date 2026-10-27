import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Button, EmptyState } from './ui'

describe('Button', () => {
  it('is disabled and shows a spinner while loading', async () => {
    const onClick = vi.fn()
    render(<Button loading onClick={onClick}>Save</Button>)
    const btn = screen.getByRole('button', { name: 'Save' })
    expect(btn).toBeDisabled()
    await userEvent.click(btn)
    expect(onClick).not.toHaveBeenCalled()
  })
})

describe('EmptyState', () => {
  it('renders title, hint and action', () => {
    render(<EmptyState title="No tickets" hint="Raise one" action={<button>New</button>} />)
    expect(screen.getByText('No tickets')).toBeInTheDocument()
    expect(screen.getByText('Raise one')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'New' })).toBeInTheDocument()
  })
})
