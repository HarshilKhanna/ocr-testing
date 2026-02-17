'use client'

import { QueryPanel } from './query-panel'
import { PDFViewer } from './pdf-viewer'

interface WorkspaceProps {
  pdfUrl?: string
  onQuery?: (serialNumber: string) => void
  result?: {
    text: string
    engine?: string
    totalCases?: number
    extractionTime?: number
  }
  isLoading?: boolean
}

export function Workspace({
  pdfUrl,
  onQuery,
  result,
  isLoading,
}: WorkspaceProps) {
  return (
    <div className="h-screen grid grid-cols-[1fr_300px] gap-4 bg-background p-4">
      {/* Left Panel - PDF Viewer (70%) */}
      <div className="overflow-hidden">
        <PDFViewer pdfUrl={pdfUrl} />
      </div>

      {/* Right Panel - Query Panel (30%) */}
      <div className="flex flex-col gap-4 overflow-hidden rounded border border-border bg-card p-4">
        <QueryPanel
          onQuery={onQuery || (() => {})}
          result={result}
          isLoading={isLoading}
        />
      </div>
    </div>
  )
}
