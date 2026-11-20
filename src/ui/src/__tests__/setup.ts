import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

// Dates are rendered with toLocaleDateString; a fixed zone keeps snapshots stable.
process.env.TZ = 'UTC'

afterEach(() => {
  cleanup()
  localStorage.clear()
})
