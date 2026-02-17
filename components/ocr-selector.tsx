'use client'

import { Radio } from 'lucide-react'

interface OCRSelectorProps {
  selectedEngine: string | null
  onEngineSelect: (engine: string) => void
}

const engines = [
  {
    id: 'azure',
    name: 'Azure Document Intelligence',
    description: 'High-accuracy cloud-based document OCR.',
  },
  {
    id: 'paddle',
    name: 'PaddleOCR',
    description: 'Open-source deep-learning based OCR engine.',
  },
  {
    id: 'tesseract',
    name: 'Tesseract (Local)',
    description: 'Lightweight open-source OCR engine.',
  },
]

export function OCRSelector({
  selectedEngine,
  onEngineSelect,
}: OCRSelectorProps) {
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-foreground">OCR Engine</h3>
      <div className="grid gap-3">
        {engines.map((engine) => (
          <button
            key={engine.id}
            onClick={() => onEngineSelect(engine.id)}
            className={`flex items-start gap-4 rounded border p-4 text-left transition-colors ${
              selectedEngine === engine.id
                ? 'border-primary bg-secondary'
                : 'border-border bg-card hover:bg-secondary'
            }`}
          >
            <div className="mt-1 flex-shrink-0">
              <div
                className={`h-4 w-4 rounded-full border-2 ${
                  selectedEngine === engine.id
                    ? 'border-primary bg-primary'
                    : 'border-border'
                }`}
              />
            </div>
            <div className="flex-1">
              <h4 className="font-semibold text-foreground">{engine.name}</h4>
              <p className="text-sm text-muted-foreground">{engine.description}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
