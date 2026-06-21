"use client"

import { useState, useRef, type ChangeEvent } from "react"
import { Upload, FileText, Loader2, Check, AlertTriangle, X } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import { exportBatchResultsToCsv } from "@/lib/export"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"

const INDUSTRIES = [
  { value: "general", label: "通用" },
  { value: "food", label: "食品饮料" },
  { value: "cosmetic", label: "化妆品" },
  { value: "medicine", label: "医疗健康" },
  { value: "education", label: "教育培训" },
  { value: "finance", label: "金融理财" },
  { value: "real_estate", label: "房地产" },
  { value: "ecommerce", label: "电子商务" },
]

interface BatchResultItem {
  index: number
  text: string
  status: string
  overall_risk: string
  violation_count: number
  violations: { text: string; category: string; severity: string; suggestion: string }[]
  error?: string
}

interface BatchUploadProps {
  onResults: (results: BatchResultItem[]) => void
  disabled?: boolean
}

export function BatchUpload({ onResults, disabled }: BatchUploadProps) {
  const [file, setFile] = useState<File | null>(null)
  const [industry, setIndustry] = useState("general")
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [statusText, setStatusText] = useState("")
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) setFile(f)
    setError(null)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const f = e.dataTransfer.files?.[0]
    if (f && (f.name.endsWith(".txt") || f.name.endsWith(".csv"))) {
      setFile(f)
      setError(null)
    } else {
      setError("仅支持 .txt 和 .csv 文件")
    }
  }

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setProgress(0)
    setError(null)
    setStatusText("正在上传文件…")

    const token = typeof window !== "undefined" ? localStorage.getItem("ad_agent_token") : null
    const apiKey = typeof window !== "undefined" ? localStorage.getItem("ad_agent_api_key") || "" : ""
    const baseUrl = typeof window !== "undefined" ? localStorage.getItem("ad_agent_base_url") || "" : ""
    const model = typeof window !== "undefined" ? localStorage.getItem("ad_agent_model") || "" : ""

    const formData = new FormData()
    formData.append("file", file)
    formData.append("industry", industry)
    if (apiKey) formData.append("api_key", apiKey)
    if (baseUrl) formData.append("base_url", baseUrl)
    if (model) formData.append("model", model)

    try {
      setStatusText("正在提交审查…")
      const headers: Record<string, string> = {}
      if (token) headers["Authorization"] = `Bearer ${token}`

      const res = await fetch(`${API_BASE}/api/batch-review`, {
        method: "POST",
        headers,
        body: formData,
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || `请求失败 (${res.status})`)
      }

      const data = await res.json()
      setProgress(100)
      setStatusText(`审查完成 · 共 ${data.total} 条`)
      onResults(data.results || [])
    } catch (err: any) {
      setError(err.message || "批量审查失败")
    } finally {
      setUploading(false)
    }
  }

  const lineCount = file
    ? (file.name.endsWith(".csv")
        ? "CSV 文件"
        : "TXT 文件")
    : 0

  return (
    <Card>
      <CardContent className="space-y-4 pt-6">
        <div
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          onClick={() => inputRef.current?.click()}
          className={`flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-8 transition-colors cursor-pointer
            ${file ? "border-[#0066ff]/30 bg-[#0066ff]/5" : "border-muted-foreground/20 hover:border-muted-foreground/40 bg-muted/20"}
          `}
        >
          {file ? (
            <div className="flex items-center gap-3">
              <FileText className="size-8 text-[#0066ff]" />
              <div>
                <p className="text-sm font-medium">{file.name}</p>
                <p className="text-xs text-muted-foreground">{(file.size / 1024).toFixed(1)} KB</p>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); setFile(null); setError(null) }}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="size-4" />
              </button>
            </div>
          ) : (
            <>
              <Upload className="size-8 text-muted-foreground/50" />
              <div className="text-center">
                <p className="text-sm font-medium">点击或拖拽文件到此处</p>
                <p className="text-xs text-muted-foreground mt-1">支持 .txt / .csv 格式，最多 100 条文案</p>
              </div>
            </>
          )}
          <input
            ref={inputRef}
            type="file"
            accept=".txt,.csv"
            onChange={handleFileChange}
            className="hidden"
          />
        </div>

        <div className="flex items-end gap-3">
          <div className="flex-1 space-y-1.5">
            <label className="text-xs font-medium">所属行业</label>
            <Select value={industry} onValueChange={(v) => setIndustry(v ?? "general")}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {INDUSTRIES.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <Button
            onClick={handleUpload}
            disabled={!file || uploading || disabled}
            className="shrink-0"
          >
            {uploading ? <><Loader2 className="size-4 animate-spin" /> 审查中…</> : <><Upload className="size-4" /> 开始批量审查</>}
          </Button>
        </div>

        {uploading && progress > 0 && (
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{statusText}</span>
              <span>{progress}%</span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
              <div className="h-full rounded-full bg-primary transition-all duration-500" style={{ width: `${Math.max(progress, 5)}%` }} />
            </div>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-700">
            <AlertTriangle className="size-3.5 shrink-0" />
            {error}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
