'use client'

import { Upload } from 'lucide-react'
import { useRef, useState } from 'react'

interface UploadAreaProps {
  onFileSelect: (file: File) => void
  isLoading?: boolean
}

export function UploadArea({ onFileSelect, isLoading }: UploadAreaProps) {
  const [isDragActive, setIsDragActive] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setIsDragActive(true)
    } else if (e.type === 'dragleave') {
      setIsDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragActive(false)

    const files = e.dataTransfer.files
    if (files && files[0]?.type === 'application/pdf') {
      onFileSelect(files[0])
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files[0]) {
      onFileSelect(files[0])
    }
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-foreground">Upload PDF</h3>
      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        className={`cursor-pointer rounded border-2 border-dashed p-8 text-center transition-colors ${
          isDragActive
            ? 'border-primary bg-card'
            : 'border-border bg-card'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          onChange={handleChange}
          className="hidden"
          disabled={isLoading}
        />
        <button
          onClick={() => inputRef.current?.click()}
          disabled={isLoading}
          className="flex flex-col items-center gap-2 w-full"
        >
          <Upload className="h-8 w-8 text-muted-foreground" />
          <p className="font-semibold text-foreground">
            Drag & drop your cause list PDF here
          </p>
          <p className="text-sm text-muted-foreground">or click to browse</p>
          <p className="text-xs text-muted-foreground">Supported format: PDF only</p>
        </button>
      </div>
    </div>
  )
}
