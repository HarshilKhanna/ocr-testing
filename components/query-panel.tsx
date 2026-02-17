'use client'

import { useState } from 'react'
import { ResultBlock } from './result-block'

interface QueryPanelProps {
  onQuery: (serialNumber: string) => void
  result?: {
    text: string
    engine?: string
    totalCases?: number
    extractionTime?: number
  }
  isLoading?: boolean
}

export function QueryPanel({
  onQuery,
  result,
  isLoading,
}: QueryPanelProps) {
  const [serialNumber, setSerialNumber] = useState('')

  const handleRetrieve = () => {
    if (serialNumber.trim()) {
      onQuery(serialNumber)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleRetrieve()
    }
  }

  return (
    <div className="flex h-full flex-col space-y-6 overflow-y-auto">
      {/* Query Section */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-foreground">Case Retrieval</h3>

        <div className="space-y-2">
          <label className="block text-sm text-foreground">
            Enter Serial Number
          </label>
          <input
            type="text"
            value={serialNumber}
            onChange={(e) => setSerialNumber(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="e.g. 5"
            disabled={isLoading}
            className="w-full rounded border border-border bg-secondary px-3 py-2 text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <button
          onClick={handleRetrieve}
          disabled={!serialNumber.trim() || isLoading}
          className={`w-full rounded py-2 font-semibold text-white transition-colors ${
            serialNumber.trim() && !isLoading
              ? 'bg-primary hover:bg-blue-700 active:bg-blue-800'
              : 'bg-muted cursor-not-allowed text-muted-foreground'
          }`}
        >
          Retrieve Case
        </button>
      </div>

      {/* Result Section */}
      <div className="flex-1 overflow-hidden">
        <ResultBlock result={result} isLoading={isLoading} />
      </div>
    </div>
  )
}
