'use client'

import { useState } from 'react'
import { HeroPage } from '@/components/hero-page'
import { Workspace } from '@/components/workspace'

interface ExtractedData {
  text: string
  engine: string
  totalCases: number
  extractionTime: number
}

export default function Page() {
  const [stage, setStage] = useState<'hero' | 'workspace'>('hero')
  const [selectedEngine, setSelectedEngine] = useState<string>('')
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [extractedData, setExtractedData] = useState<ExtractedData | null>(null)
  const [queryResult, setQueryResult] = useState<ExtractedData | null>(null)
  const [isQuerying, setIsQuerying] = useState(false)

  const handleUpload = async (file: File, engine: string) => {
    setIsProcessing(true)
    setSelectedEngine(engine)
    setUploadedFile(file)

    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('selected_engine', engine)

      const res = await fetch('http://localhost:8000/upload', {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Upload failed' }))
        throw new Error(err.detail || 'Upload failed')
      }

      const data = await res.json()

      setExtractedData({
        text: `Processed with ${data.engine_used}\nTotal cases: ${data.total_cases_detected}\nPages: ${data.pages_processed}\nTime: ${data.extraction_time}s`,
        engine: data.engine_used,
        totalCases: data.total_cases_detected,
        extractionTime: data.extraction_time,
      })
      setStage('workspace')
    } catch (error: any) {
      alert(error.message || 'Upload failed')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleQuery = async (serialNumber: string) => {
    setIsQuerying(true)

    try {
      const res = await fetch(`http://localhost:8000/case?sno=${serialNumber}`)

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Case not found' }))
        setQueryResult({
          text: err.detail || `No case found with serial number ${serialNumber}`,
          engine: extractedData?.engine || 'Unknown',
          totalCases: extractedData?.totalCases || 0,
          extractionTime: 0,
        })
        return
      }

      const data = await res.json()

      setQueryResult({
        text: data.content,
        engine: extractedData?.engine || 'Unknown',
        totalCases: extractedData?.totalCases || 0,
        extractionTime: extractedData?.extractionTime || 0,
      })
    } catch (error: any) {
      setQueryResult({
        text: error.message || 'Query failed',
        engine: extractedData?.engine || 'Unknown',
        totalCases: extractedData?.totalCases || 0,
        extractionTime: 0,
      })
    } finally {
      setIsQuerying(false)
    }
  }

  const handleReset = () => {
    setStage('hero')
    setExtractedData(null)
    setQueryResult(null)
    setSelectedEngine('')
    setUploadedFile(null)
  }

  if (stage === 'hero') {
    return <HeroPage onUpload={handleUpload} isLoading={isProcessing} />
  }

  return (
    <div>
      <div className="border-b border-border bg-card px-6 py-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">
          Supreme Court Cause List Processor
        </h2>
        <button
          onClick={handleReset}
          className="rounded border border-primary bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-blue-700 active:bg-blue-800 transition-colors"
        >
          New Upload
        </button>
      </div>
      <Workspace
        pdfUrl={uploadedFile ? URL.createObjectURL(uploadedFile) : undefined}
        onQuery={handleQuery}
        result={queryResult}
        isLoading={isQuerying}
      />
    </div>
  )
}
