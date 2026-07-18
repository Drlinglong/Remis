import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { vendorLogos } from './vendorLogos'

const websiteRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const vendorAssetDirectory = path.join(websiteRoot, 'public', 'assets', 'vendors')

describe('vendor logo catalog', () => {
  it('has one catalog entry for every shipped vendor asset', () => {
    const catalogFiles = Object.values(vendorLogos).map(({ file }) => file).sort()
    const assetFiles = fs.readdirSync(vendorAssetDirectory).sort()

    expect(catalogFiles).toEqual(assetFiles)
  })

  it('uses stable vendor ids and base-aware asset URLs', () => {
    for (const [vendorId, logo] of Object.entries(vendorLogos)) {
      expect(logo.id).toBe(vendorId)
      expect(logo.label).not.toBe('')
      expect(logo.src).toContain(`/assets/vendors/${logo.file}`)
    }
  })
})
