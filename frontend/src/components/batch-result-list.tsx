"use client"

import { useState } from "react"
import { ChevronDown, ChevronRight, ShieldCheck, AlertTriangle, Download, RotateCcw } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { exportBatchResultsToCsv } from "@/lib/export"

interface BatchViolation {
  text: string
  category: string
  severity: string
  suggestion: string
}

interface BatchResultItem {
  index: number
  text: string
  status: string
  overall_risk: string
  violation_count: number
  violations: BatchViolation[]
  error?: string
}

const RISK_BADGE: Record<string, string> = {
  high: "bg-red-100 text-red-800 border-red-300",
  medium: "bg-amber-100 text-amber-800 border-amber-300",
  low: "bg-green-100 text-green-800 border-green-300",
  pass: "bg-gray-100 text-gray-700 border-gray-300",
  error: "bg-red-50 text-red-500 border-red-200",
}

const RISK_LABEL: Record<string, string> = {
  high: "高风险",
  medium: "中风险",
  low: "低风险",
  pass: "通过",
  error: "错误",
}

function BatchResultRow({ item }: { item: BatchResultItem }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <Card className="border-l-4 overflow-hidden" style={{
      borderLeftColor: item.status === "error" ? "#ef4444" :
        item.overall_risk === "high" ? "#ef4444" :
        item.overall_risk === "medium" ? "#f59e0b" :
        item.overall_risk === "low" ? "#22c55e" : "#9ca3af"
    }}>
      <button onClick={() => setExpanded(!expanded)} className="w-full text-left cursor-pointer">
        <CardContent className="flex items-center gap-3 py-3 pr-4">
          <span className="text-xs font-mono text-muted-foreground w-6 shrink-0">#{item.index}</span>
          <p className="text-sm flex-1 truncate">{item.text}</p>
          <Badge variant="outline" className={`text-xs shrink-0 ${RISK_BADGE[item.overall_risk] || ""}`}>
            {RISK_LABEL[item.overall_risk] || item.overall_risk}
          </Badge>
          <span className="text-xs text-muted-foreground tabular-nums shrink-0 w-12 text-right">
            {item.status === "error" ? "-" : `${item.violation_count}项`}
          </span>
          {expanded ? <ChevronDown className="size-3.5 text-muted-foreground shrink-0" /> : <ChevronRight className="size-3.5 text-muted-foreground shrink-0" />}
        </CardContent>
      </button>

      {expanded && (
        <CardContent className="pt-0 pb-3 space-y-2 border-t">
          {item.status === "error" ? (
            <div className="flex items-center gap-2 text-xs text-red-600 pt-2">
              <AlertTriangle className="size-3" />
              {item.error || "审查异常"}
            </div>
          ) : item.violations.length === 0 ? (
            <p className="text-xs text-emerald-600 pt-2 flex items-center gap-1">
              <ShieldCheck className="size-3" /> 未检测到违规
            </p>
          ) : (
            <div className="pt-2 space-y-1.5">
              {item.violations.map((v, i) => (
                <div key={i} className="flex items-start gap-2 rounded-md bg-muted/30 p-2 text-xs">
                  <Badge variant="outline" className={`shrink-0 text-[10px] ${
                    v.severity === "high" ? "border-red-300 text-red-700 bg-red-50" :
                    v.severity === "medium" ? "border-amber-300 text-amber-700 bg-amber-50" :
                    "border-green-300 text-green-700 bg-green-50"
                  }`}>
                    {v.category}
                  </Badge>
                  <div className="flex-1 min-w-0 space-y-0.5">
                    <p className="font-medium truncate">{v.text}</p>
                    {v.suggestion && (
                      <p className="text-emerald-700">
                        建议：{v.suggestion}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      )}
    </Card>
  )
}

interface BatchResultListProps {
  results: BatchResultItem[]
  summary: { high: number; medium: number; low: number; pass: number; error: number }
  onReset: () => void
}

export function BatchResultList({ results, summary, onReset }: BatchResultListProps) {
  return (
    <div className="space-y-4">
      {/* Summary */}
      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="size-5 text-primary" />
            <span className="text-sm font-medium">批量审查结果</span>
            <span className="text-xs text-muted-foreground">共 {results.length} 条</span>
          </div>
          <div className="flex items-center gap-2">
            {summary.high > 0 && <Badge className="bg-red-100 text-red-800 border-red-300">{summary.high} 高风险</Badge>}
            {summary.medium > 0 && <Badge className="bg-amber-100 text-amber-800 border-amber-300">{summary.medium} 中风险</Badge>}
            {summary.low > 0 && <Badge className="bg-green-100 text-green-800 border-green-300">{summary.low} 低风险</Badge>}
            {summary.pass > 0 && <Badge className="bg-gray-100 text-gray-700 border-gray-300">{summary.pass} 通过</Badge>}
            {summary.error > 0 && <Badge className="bg-red-50 text-red-500 border-red-200">{summary.error} 错误</Badge>}
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      <div className="space-y-2">
        {results.map((item) => (
          <BatchResultRow key={item.index} item={item} />
        ))}
      </div>

      {/* Actions */}
      <div className="flex justify-center gap-3">
        <Button variant="outline" onClick={() => exportBatchResultsToCsv(results)}>
          <Download className="size-4" /> 导出 CSV
        </Button>
        <Button variant="outline" onClick={onReset}>
          <RotateCcw className="size-4" /> 重新上传
        </Button>
      </div>
    </div>
  )
}
