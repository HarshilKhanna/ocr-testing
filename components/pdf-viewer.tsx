'use client'

interface PDFViewerProps {
  pdfUrl?: string
}

export function PDFViewer({ pdfUrl }: PDFViewerProps) {
  return (
    <div className="flex h-full flex-col bg-secondary p-4">
      {pdfUrl ? (
        <div className="flex-1 overflow-hidden rounded border border-border bg-white">
          <iframe
            src={pdfUrl}
            className="h-full w-full"
            title="PDF Viewer"
          />
        </div>
      ) : (
        <div className="flex flex-1 items-center justify-center rounded border border-border bg-white">
          <div className="text-center">
            <p className="text-muted-foreground">PDF preview will appear here</p>
          </div>
        </div>
      )}
    </div>
  )
}
