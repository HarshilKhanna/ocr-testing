'use client'

import { useState } from 'react'
import { OCRSelector } from './ocr-selector'
import { UploadArea } from './upload-area'

interface HeroPageProps {
  onUpload: (file: File, engine: string) => void
  isLoading?: boolean
}

export function HeroPage({ onUpload, isLoading }: HeroPageProps) {
  const [selectedEngine, setSelectedEngine] = useState<string | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  const handleProcess = () => {
    if (selectedFile && selectedEngine) {
      onUpload(selectedFile, selectedEngine)
    }
  }

  const isReady = selectedFile && selectedEngine

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-2xl px-6 py-16 sm:py-24">
        {/* Header Section */}
        <div className="mb-12 text-center">
          <h1 className="mb-2 text-4xl font-bold text-foreground">
            Supreme Court Cause List Processor
          </h1>
          <p className="mb-2 text-lg text-foreground">
            Upload a cause list PDF and select an OCR engine to extract cases by serial number.
          </p>
          <p className="text-sm text-muted-foreground">
            Deterministic extraction. No generative AI used.
          </p>
        </div>

        {/* Form Section */}
        <div className="space-y-8 rounded border border-border bg-card p-8">
          {/* OCR Engine Selection */}
          <OCRSelector
            selectedEngine={selectedEngine}
            onEngineSelect={setSelectedEngine}
          />

          {/* File Upload */}
          <UploadArea
            onFileSelect={setSelectedFile}
            isLoading={isLoading}
          />

          {/* Selected File Display */}
          {selectedFile && (
            <div className="rounded bg-secondary p-3">
              <p className="text-sm text-foreground">
                <span className="font-semibold">Selected:</span> {selectedFile.name}
              </p>
            </div>
          )}

          {/* Process Button */}
          <button
            onClick={handleProcess}
            disabled={!isReady || isLoading}
            className={`w-full rounded py-3 font-semibold text-white transition-colors ${
              isReady && !isLoading
                ? 'bg-primary hover:bg-blue-700 active:bg-blue-800'
                : 'bg-muted cursor-not-allowed text-muted-foreground'
            }`}
          >
            {isLoading ? (
              <div className="flex items-center justify-center gap-2">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                <span>Processing document...</span>
              </div>
            ) : (
              'Upload & Process'
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
