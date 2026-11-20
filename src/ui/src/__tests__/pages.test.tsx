/**
 * Characterization tests for the UI pages. Each test renders a page in one
 * state and pins its markup and where its buttons navigate, so the pages can
 * be split into smaller components without changing what users see.
 */
import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../lib/api'
import { BARE_DOC, DOC, renderAt } from './render'

vi.mock('../lib/api', () => ({
  api: {
    uploadDocument: vi.fn(),
    getDocumentMetadata: vi.fn(),
    anonymizeDocument: vi.fn(),
    downloadDocument: vi.fn(),
    getDocumentDownloadUrl: vi.fn((id: string) => `http://api/documents/${id}/download`),
    deanonymizeDocument: vi.fn(),
  },
}))

const mocked = vi.mocked(api)
const location = () => screen.getByTestId('location').textContent

beforeEach(() => {
  vi.clearAllMocks()
})

describe('HomePage', () => {
  it('shows the empty list', () => {
    const { container } = renderAt('/')
    expect(container.innerHTML).toMatchSnapshot()
  })

  it('lists stored documents, also under the old storage key', () => {
    localStorage.setItem('openAnonymiser_docs', JSON.stringify([DOC, BARE_DOC]))
    const { container } = renderAt('/')
    expect(container.innerHTML).toMatchSnapshot()
    expect(JSON.parse(localStorage.getItem('anonymiq_docs') ?? '[]')).toHaveLength(2)
  })

  it('ignores a stored list that is not JSON', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    localStorage.setItem('anonymiq_docs', '{broken')
    renderAt('/')
    expect(screen.getByText('No documents uploaded yet')).toBeTruthy()
    expect(spy).toHaveBeenCalled()
    spy.mockRestore()
  })

  it('uploads a file with tags and puts it first in the list', async () => {
    localStorage.setItem('anonymiq_docs', JSON.stringify([BARE_DOC]))
    mocked.uploadDocument.mockResolvedValue([DOC])
    const { container } = renderAt('/')
    const file = new File(['%PDF'], 'brief.pdf', { type: 'application/pdf' })
    const input = container.querySelector('input[type=file]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    fireEvent.change(screen.getByLabelText('Tags (comma separated)'), {
      target: { value: ' personal, ,finance ' },
    })
    fireEvent.click(screen.getByText('Upload Document', { selector: 'button' }))
    await screen.findByText('2 uploaded')
    expect(mocked.uploadDocument).toHaveBeenCalledWith(file, ['personal', 'finance'])
    expect(container.innerHTML).toMatchSnapshot()
  })

  it('asks for a file before uploading', async () => {
    renderAt('/')
    fireEvent.click(screen.getByText('Upload Document', { selector: 'button' }))
    expect(await screen.findByText('Please select a file')).toBeTruthy()
    expect(mocked.uploadDocument).not.toHaveBeenCalled()
  })

  it('shows an upload error', async () => {
    mocked.uploadDocument.mockRejectedValue(new Error('Failed to upload document'))
    const { container } = renderAt('/')
    const input = container.querySelector('input[type=file]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [new File(['x'], 'a.pdf')] } })
    fireEvent.click(screen.getByText('Upload Document', { selector: 'button' }))
    await screen.findByText('Failed to upload document')
    expect(container.innerHTML).toMatchSnapshot()
  })

  it('opens and anonymizes a listed document', () => {
    localStorage.setItem('anonymiq_docs', JSON.stringify([DOC]))
    renderAt('/')
    fireEvent.click(screen.getByText('View Details'))
    expect(location()).toBe('/document/abc123')
  })

  it('goes to the anonymize page from a card', () => {
    localStorage.setItem('anonymiq_docs', JSON.stringify([DOC]))
    renderAt('/')
    fireEvent.click(screen.getByText('Anonymize', { selector: 'button' }))
    expect(location()).toBe('/document/anonymize/abc123')
  })
})

describe('DocumentPage', () => {
  it('shows the loading state', () => {
    mocked.getDocumentMetadata.mockReturnValue(new Promise(() => {}))
    const { container } = renderAt('/document/abc123')
    expect(container.innerHTML).toMatchSnapshot()
    expect(mocked.getDocumentMetadata).toHaveBeenCalledWith('abc123', true)
  })

  it('shows a load error and goes back', async () => {
    mocked.getDocumentMetadata.mockRejectedValue(new Error('Failed to get document metadata'))
    const { container } = renderAt('/document/abc123')
    await screen.findByText('Failed to get document metadata')
    expect(container.innerHTML).toMatchSnapshot()
    fireEvent.click(screen.getByText('Back to Documents'))
    expect(location()).toBe('/')
  })

  it('shows the document', async () => {
    mocked.getDocumentMetadata.mockResolvedValue(DOC)
    const { container } = renderAt('/document/abc123')
    await screen.findByText('Document Details')
    expect(container.innerHTML).toMatchSnapshot()
  })

  it('shows a document without tags or entities', async () => {
    mocked.getDocumentMetadata.mockResolvedValue(BARE_DOC)
    const { container } = renderAt('/document/bare1')
    await screen.findByText('Document Details')
    expect(container.innerHTML).toMatchSnapshot()
  })

  it('navigates from the document view', async () => {
    mocked.getDocumentMetadata.mockResolvedValue(DOC)
    renderAt('/document/abc123')
    fireEvent.click(await screen.findByText('View Details'))
    expect(location()).toBe('/document/abc123?view=details')
    fireEvent.click(await screen.findByText('Back to Document'))
    expect(location()).toBe('/document/abc123')
    fireEvent.click(await screen.findByText('Anonymize Document'))
    expect(location()).toBe('/document/anonymize/abc123')
  })

  it('shows the detailed view', async () => {
    mocked.getDocumentMetadata.mockResolvedValue(DOC)
    const { container } = renderAt('/document/abc123?view=details')
    await screen.findByText('Document Metadata')
    expect(container.innerHTML).toMatchSnapshot()
    fireEvent.click(screen.getByText('Anonymize Document'))
    expect(location()).toBe('/document/anonymize/abc123')
  })

  it('shows the detailed view without tags or entities', async () => {
    mocked.getDocumentMetadata.mockResolvedValue(BARE_DOC)
    const { container } = renderAt('/document/bare1?view=details')
    await screen.findByText('Document Metadata')
    expect(container.innerHTML).toMatchSnapshot()
  })
})

describe('AnonymizePage', () => {
  it('shows the loading state', () => {
    mocked.getDocumentMetadata.mockReturnValue(new Promise(() => {}))
    const { container } = renderAt('/document/anonymize/abc123')
    expect(container.innerHTML).toMatchSnapshot()
  })

  it('shows a load error', async () => {
    mocked.getDocumentMetadata.mockRejectedValue('not an error')
    const { container } = renderAt('/document/anonymize/abc123')
    await screen.findByText('Failed to load document')
    expect(container.innerHTML).toMatchSnapshot()
  })

  it('shows the entity types to choose from', async () => {
    mocked.getDocumentMetadata.mockResolvedValue(DOC)
    const { container } = renderAt('/document/anonymize/abc123')
    await screen.findByText('Select PII Entity Types to Anonymize')
    expect(container.innerHTML).toMatchSnapshot()
  })

  it('shows a document without entities', async () => {
    mocked.getDocumentMetadata.mockResolvedValue(BARE_DOC)
    const { container } = renderAt('/document/anonymize/bare1')
    await screen.findByText('No PII entities detected in this document')
    expect(container.innerHTML).toMatchSnapshot()
  })

  it('anonymizes the selected types', async () => {
    mocked.getDocumentMetadata.mockResolvedValue(DOC)
    mocked.anonymizeDocument.mockResolvedValue({ status: 'success (2 entities processed)', time_taken: 42 })
    const { container } = renderAt('/document/anonymize/abc123')
    fireEvent.click(await screen.findByLabelText('EMAIL (1)'))
    fireEvent.click(screen.getByLabelText('PERSON (2)'))
    fireEvent.click(screen.getByLabelText('EMAIL (1)'))
    fireEvent.click(screen.getByLabelText('EMAIL (1)'))
    expect(container.innerHTML).toMatchSnapshot()
    fireEvent.click(screen.getByText('Anonymize Document', { selector: 'button' }))
    await screen.findByText('Anonymization Complete')
    expect(mocked.anonymizeDocument).toHaveBeenCalledWith('abc123', ['PERSON', 'EMAIL'])
    expect(container.innerHTML).toMatchSnapshot()
    fireEvent.click(screen.getByText('Back to Documents', { selector: 'div.flex.justify-between button' }))
    expect(location()).toBe('/')
  })

  it('shows an anonymization error', async () => {
    mocked.getDocumentMetadata.mockResolvedValue(DOC)
    mocked.anonymizeDocument.mockRejectedValue(new Error('Failed to anonymize document'))
    const { container } = renderAt('/document/anonymize/abc123')
    fireEvent.click(await screen.findByLabelText('PERSON (2)'))
    fireEvent.click(screen.getByText('Anonymize Document', { selector: 'button' }))
    await screen.findByText('Failed to anonymize document')
    expect(container.innerHTML).toMatchSnapshot()
  })

  it('shows the busy state while anonymizing', async () => {
    mocked.getDocumentMetadata.mockResolvedValue(DOC)
    mocked.anonymizeDocument.mockReturnValue(new Promise(() => {}))
    const { container } = renderAt('/document/anonymize/abc123')
    fireEvent.click(await screen.findByLabelText('PERSON (2)'))
    fireEvent.click(screen.getByText('Anonymize Document', { selector: 'button' }))
    await screen.findByText('Processing...')
    expect(container.innerHTML).toMatchSnapshot()
  })

  it('cancels back to the list', async () => {
    mocked.getDocumentMetadata.mockResolvedValue(DOC)
    renderAt('/document/anonymize/abc123')
    fireEvent.click(await screen.findByText('Cancel'))
    expect(location()).toBe('/')
  })
})

describe('DeanonymizePage', () => {
  it('shows the form and goes back', () => {
    const { container } = renderAt('/deanonymize')
    expect(container.innerHTML).toMatchSnapshot()
    fireEvent.click(screen.getByText('Back to Documents'))
    expect(location()).toBe('/')
  })

  it('downloads the restored document', async () => {
    const blob = new Blob(['%PDF'])
    mocked.deanonymizeDocument.mockResolvedValue(blob)
    const createObjectURL = vi.fn(() => 'blob:restored')
    const revokeObjectURL = vi.fn()
    Object.assign(URL, { createObjectURL, revokeObjectURL })
    const clicks: string[] = []
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(function (this: HTMLAnchorElement) {
        clicks.push(`${this.href} ${this.download}`)
      })
    const { container } = renderAt('/deanonymize')
    const file = new File(['%PDF'], 'anon.pdf')
    fireEvent.change(container.querySelector('input[type=file]') as HTMLInputElement, {
      target: { files: [file] },
    })
    await act(async () => {
      fireEvent.click(screen.getByText('Deanonymize Document', { selector: 'button' }))
    })
    await screen.findByText('Document successfully deanonymized and downloaded!')
    expect(mocked.deanonymizeDocument).toHaveBeenCalledWith(file)
    expect(clicks).toEqual(['blob:restored deanonymized_anon.pdf'])
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:restored')
    expect(container.innerHTML).toMatchSnapshot()
    click.mockRestore()
  })

  it('shows a deanonymization error', async () => {
    mocked.deanonymizeDocument.mockRejectedValue(new Error('Failed to deanonymize document'))
    const { container } = renderAt('/deanonymize')
    fireEvent.change(container.querySelector('input[type=file]') as HTMLInputElement, {
      target: { files: [new File(['x'], 'a.pdf')] },
    })
    fireEvent.click(screen.getByText('Deanonymize Document', { selector: 'button' }))
    await waitFor(() => expect(screen.getByText('Failed to deanonymize document')).toBeTruthy())
    expect(container.innerHTML).toMatchSnapshot()
  })
})
