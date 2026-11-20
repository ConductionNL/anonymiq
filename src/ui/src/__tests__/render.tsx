import { render } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import HomePage from '../pages/index'
import DocumentPage from '../pages/document/[id]'
import AnonymizePage from '../pages/document/anonymize/[id]'
import DeanonymizePage from '../pages/deanonymize'
import type { DocumentDto } from '../types'

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location">{location.pathname + location.search}</output>
}

/** Render the app's routes at a path, with the current location exposed. */
export function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <LocationProbe />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/document/:id" element={<DocumentPage />} />
        <Route path="/document/anonymize/:id" element={<AnonymizePage />} />
        <Route path="/deanonymize" element={<DeanonymizePage />} />
      </Routes>
    </MemoryRouter>,
  )
}

export const DOC: DocumentDto = {
  id: 'abc123',
  filename: 'brief.pdf',
  content_type: 'application/pdf',
  uploaded_at: '2026-10-30T09:15:00Z',
  tags: [
    { id: 't1', name: 'personal' },
    { id: 't2', name: 'finance' },
  ],
  pii_entities: [
    { entity_type: 'PERSON', text: 'Jan Jansen', start: 0, end: 10, score: 0.853 },
    { entity_type: 'PERSON', text: 'Piet', start: 20, end: 24 },
    { entity_type: 'EMAIL', text: 'jan@example.nl', start: 30, end: 44, score: 1 },
  ],
}

export const BARE_DOC: DocumentDto = { ...DOC, id: 'bare1', tags: [], pii_entities: [] }
