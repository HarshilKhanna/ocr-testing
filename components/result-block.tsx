'use client'

interface ResultBlockProps {
  result?: {
    text: string
    engine?: string
    totalCases?: number
    extractionTime?: number
  }
  isLoading?: boolean
}

export function ResultBlock({ result, isLoading }: ResultBlockProps) {
  return (
    <div className="flex flex-col space-y-4">
      <h3 className="text-sm font-semibold text-foreground">Extracted Case Block</h3>

      {/* Metadata Section */}
      {result && (
        <div className="space-y-2 rounded bg-secondary p-3 text-sm">
          {result.engine && (
            <div>
              <span className="text-muted-foreground">Engine Used:</span>
              <span className="ml-2 font-medium text-foreground">{result.engine}</span>
            </div>
          )}
          {result.totalCases !== undefined && (
            <div>
              <span className="text-muted-foreground">Total Cases Detected:</span>
              <span className="ml-2 font-medium text-foreground">{result.totalCases}</span>
            </div>
          )}
          {result.extractionTime !== undefined && (
            <div>
              <span className="text-muted-foreground">Extraction Time:</span>
              <span className="ml-2 font-medium text-foreground">
                {result.extractionTime.toFixed(2)}s
              </span>
            </div>
          )}
        </div>
      )}

      {/* Result Text Area */}
      <textarea
        value={result?.text || ''}
        readOnly
        className="flex-1 rounded border border-border bg-secondary p-4 font-mono text-sm text-foreground placeholder-muted-foreground focus:outline-none"
        placeholder={isLoading ? 'Processing...' : 'Results will appear here'}
        style={{ minHeight: '200px', resize: 'none', whiteSpace: 'pre-wrap' }}
      />
    </div>
  )
}
