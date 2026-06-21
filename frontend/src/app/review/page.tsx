"use client"

import { useState, useCallback, useEffect, useRef } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import {
  Card, CardContent, CardHeader, CardTitle, CardDescription,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Textarea } from "@/components/ui/textarea"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import {
  ShieldCheck, Loader2, Copy, Check, X, AlertTriangle,
  FileCheck, RotateCcw, Settings, Eye, EyeOff,
  ChevronDown, ChevronRight, Zap, Brain, BookOpen, Wand2,
  CircleCheck, CircleDot, ArrowRight, Upload, Download,
} from "lucide-react"
import { submitReview, submitFeedback } from "@/lib/api"
import { BatchUpload } from "@/components/batch-upload"
import { BatchResultList } from "@/components/batch-result-list"

// ── Types ────────────────────────────────────────────────────

type RiskLevel = "high" | "medium" | "low" | "pass"
type PipelineStatus = "waiting" | "running" | "completed" | "skipped"

interface PipelineStep {
  step: number
  name: string
  status: PipelineStatus
  detail: string
  icon: string
}

interface RelatedCase {
  title: string
  penalty: string
  article: string
}

interface Violation {
  id: string
  word: string
  type: string
  law: string
  lawContent: string
  reason: string
  confidence: number
  severity: RiskLevel
  suggestion: string
  relatedCases: RelatedCase[]
}

interface ReviewResult {
  reviewId: string
  riskLevel: RiskLevel
  violations: Violation[]
  highlightedText: string
  pipelineSteps: PipelineStep[]
  processingTimeMs: number
  tokenUsage?: Record<string, number>
}

// ── Constants ────────────────────────────────────────────────

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

const SAMPLE_TEXTS = [
  { text: "全网最低价，买到就是赚到！", label: "极限用语" },
  { text: "本产品采用90%白鹅绒填充，蓬松度700+", label: "正常描述" },
  { text: "100%有效，根治痘痘，永不反弹", label: "虚假宣传" },
]

const RISK_CONFIG: Record<RiskLevel, { label: string; className: string; color: string }> = {
  high:   { label: "高风险", className: "bg-red-100 text-red-800 border-red-300", color: "text-red-600" },
  medium: { label: "中风险", className: "bg-amber-100 text-amber-800 border-amber-300", color: "text-amber-600" },
  low:    { label: "低风险", className: "bg-green-100 text-green-800 border-green-300", color: "text-green-600" },
  pass:   { label: "通过",   className: "bg-gray-100 text-gray-700 border-gray-300",   color: "text-gray-500" },
}

const STEP_ICONS: Record<number, typeof Zap> = { 1: Zap, 2: Brain, 3: BookOpen, 4: Wand2 }

// ── Pipeline Stepper ─────────────────────────────────────────

function PipelineStepper({ steps, isAnimating }: { steps: PipelineStep[]; isAnimating: boolean }) {
  return (
    <Card className="border-2 border-emerald-500/20 bg-gradient-to-br from-emerald-50/50 to-blue-50/50 dark:from-emerald-950/20 dark:to-blue-950/20">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Brain className="size-5 text-emerald-600" />
          Agent 管线执行
          {isAnimating && <Loader2 className="size-4 animate-spin text-emerald-500 ml-auto" />}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-0 pt-0">
        {steps.map((step, i) => {
          const Icon = STEP_ICONS[step.step] || Zap
          const isLast = i === steps.length - 1
          return (
            <div key={step.step} className="flex gap-3">
              {/* Timeline line */}
              <div className="flex flex-col items-center">
                <div className={`flex items-center justify-center size-8 rounded-full border-2 transition-all duration-500
                  ${step.status === "completed" ? "bg-emerald-500 border-emerald-500 text-white" :
                    step.status === "running" ? "bg-amber-100 border-amber-400 text-amber-600 animate-pulse" :
                    step.status === "skipped" ? "bg-gray-100 border-gray-300 text-gray-400" :
                    "bg-gray-50 border-gray-200 text-gray-300"}`}>
                  {step.status === "completed" ? <Check className="size-4" /> :
                   step.status === "running" ? <Loader2 className="size-4 animate-spin" /> :
                   step.status === "skipped" ? <ArrowRight className="size-3" /> :
                   <Icon className="size-3.5" />}
                </div>
                {!isLast && (
                  <div className={`w-0.5 h-8 transition-colors duration-500
                    ${step.status === "completed" ? "bg-emerald-300" : "bg-gray-200"}`} />
                )}
              </div>
              {/* Content */}
              <div className={`pb-4 min-w-0 flex-1 ${!isLast ? "" : ""}`}>
                <p className={`text-sm font-medium transition-colors duration-300
                  ${step.status === "completed" ? "text-emerald-700" :
                    step.status === "running" ? "text-amber-700" :
                    step.status === "skipped" ? "text-gray-400" : "text-gray-300"}`}>
                  {step.icon} Step {step.step}: {step.name}
                </p>
                {step.detail && (
                  <p className={`text-xs mt-0.5 transition-colors duration-300
                    ${step.status === "completed" ? "text-emerald-600/80" :
                      step.status === "running" ? "text-amber-600/80" :
                      "text-gray-400"}`}>
                    {step.detail}
                  </p>
                )}
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

// ── Confidence Bar ───────────────────────────────────────────

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const color = pct > 80 ? "bg-red-500" : pct > 50 ? "bg-amber-500" : "bg-green-500"
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-700 ${color}`}
          style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-muted-foreground w-10 text-right">{pct}%</span>
    </div>
  )
}

// ── Sanitize HTML ────────────────────────────────────────────

function sanitizeHtml(html: string): string {
  return html.replace(/<(?!\/?mark[\s>])[^>]*>/g, (m) =>
    m.replace(/</g, '&lt;').replace(/>/g, '&gt;'))
}

function exportSingleReview(result: ReviewResult) {
  const BOM = "\uFEFF"
  const now = new Date().toISOString()
  const rows = [
    ["审查ID", "整体风险", "违规数", "审查时间", "处理时间(ms)", "Token用量"].join(","),
    [
      result.reviewId,
      result.riskLevel,
      result.violations.length,
      now,
      result.processingTimeMs,
      result.tokenUsage?.totalTokens ?? result.tokenUsage?.total_tokens ?? 0,
    ].join(","),
    "",
    "违规ID,违规词,类别,风险等级,置信度,法规条文,修改建议",
    ...result.violations.map(v => [
      v.id, `"${v.word}"`, v.type, v.severity, v.confidence,
      `"${v.law}"`, v.suggestion ?? "",
    ].join(",")),
  ]
  const blob = new Blob([BOM + rows.join("\n")], { type: "text/csv;charset=utf-8;header=present" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url; a.download = `审查结果_${result.reviewId}.csv`
  a.click(); URL.revokeObjectURL(url)
}

// ── Expandable Section ───────────────────────────────────────

function ExpandableSection({
  icon, title, children, defaultOpen = false,
}: {
  icon: React.ReactNode; title: string; children: React.ReactNode; defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="rounded-lg border bg-muted/30">
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors">
        {open ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
        {icon}
        {title}
      </button>
      {open && <div className="px-3 pb-3 text-sm leading-relaxed">{children}</div>}
    </div>
  )
}

// ── Violation Card (redesigned) ──────────────────────────────

function ViolationCard({ violation, reviewId }: { violation: Violation; reviewId: string }) {
  const [copied, setCopied] = useState(false)
  const [feedback, setFeedback] = useState<"none" | "confirm" | "modify" | "dismiss">("none")
  const riskCfg = RISK_CONFIG[violation.severity]

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(violation.suggestion)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }, [violation.suggestion])

  const handleFeedback = useCallback(async (action: "confirm" | "modify" | "dismiss") => {
    setFeedback(action)
    try {
      await submitFeedback({ reviewId, violationId: violation.id, action })
    } catch { /* silent */ }
  }, [violation.id, reviewId])

  const isDismissed = feedback === "dismiss"

  return (
    <Card className={`border-l-4 transition-all duration-300
      ${isDismissed ? "opacity-50 border-l-gray-300" : violation.severity === "high" ? "border-l-red-500" : violation.severity === "medium" ? "border-l-amber-500" : "border-l-green-500"}`}>
      <CardContent className="space-y-3 pt-4">
        {/* Header */}
        <div className="flex flex-wrap items-center gap-2">
          <span className={`text-base font-semibold px-2 py-0.5 rounded ${isDismissed ? "line-through text-gray-400" : "text-red-600 bg-red-50"}`}>
            {violation.word}
          </span>
          <Badge variant="destructive" className="text-xs">{violation.type}</Badge>
          <Badge variant="outline" className={`text-xs ${riskCfg.className}`}>
            {riskCfg.label} · {Math.round(violation.confidence * 100)}%
          </Badge>
        </div>

        {/* Confidence bar */}
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">Agent 置信度</p>
          <ConfidenceBar value={violation.confidence} />
        </div>

        {/* Agent reasoning */}
        <div className="rounded-lg bg-blue-50/50 dark:bg-blue-950/20 border border-blue-200/50 px-3 py-2">
          <p className="text-xs font-medium text-blue-700 dark:text-blue-400 mb-1 flex items-center gap-1">
            <Brain className="size-3" /> Agent 判断
          </p>
          <p className="text-sm text-blue-900/80 dark:text-blue-300/80">{violation.reason}</p>
        </div>

        {/* Law article — expandable */}
        <ExpandableSection
          icon={<BookOpen className="size-3" />}
          title={`法条依据：${violation.law}`}
          defaultOpen={false}>
          <p className="text-xs text-muted-foreground mt-1 whitespace-pre-wrap">
            {violation.lawContent || "（法规全文加载中...）"}
          </p>
        </ExpandableSection>

        {/* Suggestion — 原稿 vs 改写稿对比 */}
        <div className="rounded-lg border border-emerald-200/50 overflow-hidden">
          <div className="flex items-center gap-2 bg-emerald-50/80 px-3 py-1.5 border-b border-emerald-200/50">
            <Wand2 className="size-3.5 text-emerald-600" />
            <span className="text-xs font-medium text-emerald-700">替代建议 · 原稿 vs 改写稿</span>
          </div>
          <div className="grid grid-cols-2 divide-x divide-emerald-200/50">
            <div className="p-2.5 space-y-1">
              <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide">原稿</p>
              <p className="text-sm bg-red-50 rounded px-2 py-1 text-red-800 line-through decoration-red-400">
                {violation.word}
              </p>
            </div>
            <div className="p-2.5 space-y-1">
              <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide">改写稿</p>
              <p className="text-sm bg-emerald-50 rounded px-2 py-1 text-emerald-800 font-medium">
                {violation.suggestion}
              </p>
            </div>
          </div>
          <div className="flex justify-end px-2.5 pb-2">
            <Button variant="ghost" size="icon" className="size-7" onClick={handleCopy}>
              {copied ? <Check className="size-3 text-emerald-600" /> : <Copy className="size-3" />}
            </Button>
          </div>
        </div>

        {/* Related cases */}
        {violation.relatedCases.length > 0 && (
          <ExpandableSection
            icon={<BookOpen className="size-3" />}
            title={`相关判例（${violation.relatedCases.length} 例）`}
            defaultOpen={false}>
            <div className="space-y-2 mt-1">
              {violation.relatedCases.map((c, i) => (
                <div key={i} className="rounded border bg-background/50 p-2 text-xs space-y-0.5">
                  <p className="font-medium">{c.title}</p>
                  <p className="text-muted-foreground">处罚：{c.penalty}</p>
                  {c.article && <p className="text-muted-foreground">依据：{c.article}</p>}
                </div>
              ))}
            </div>
          </ExpandableSection>
        )}

        {/* Feedback buttons */}
        <div className="flex flex-wrap gap-2 pt-1 border-t">
          {feedback === "none" ? (
            <>
              <Button size="sm" variant="default" className="h-7 text-xs" onClick={() => handleFeedback("confirm")}>
                <Check className="size-3" /> 确认违规
              </Button>
              <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => handleFeedback("modify")}>
                <AlertTriangle className="size-3" /> 修改建议
              </Button>
              <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => handleFeedback("dismiss")}>
                <X className="size-3" /> 驳回
              </Button>
            </>
          ) : (
            <span className="text-xs text-muted-foreground flex items-center gap-1">
              <Check className="size-3 text-emerald-500" />
              已反馈：{feedback === "confirm" ? "确认违规" : feedback === "modify" ? "已修改" : "已驳回"}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

// ── Settings Panel ───────────────────────────────────────────

function SettingsPanel() {
  const [apiKey, setApiKey] = useState(
    typeof window !== "undefined" ? localStorage.getItem("ad_agent_api_key") || "" : "")
  const [baseUrl, setBaseUrl] = useState(
    typeof window !== "undefined" ? localStorage.getItem("ad_agent_base_url") || "https://api.deepseek.com" : "https://api.deepseek.com")
  const [model, setModel] = useState(
    typeof window !== "undefined" ? localStorage.getItem("ad_agent_model") || "deepseek-chat" : "deepseek-chat")
  const [showKey, setShowKey] = useState(false)
  const [open, setOpen] = useState(false)
  const [saved, setSaved] = useState(false)
  const hasKey = typeof window !== "undefined" && !!localStorage.getItem("ad_agent_api_key")

  const handleSave = () => {
    localStorage.setItem("ad_agent_api_key", apiKey)
    localStorage.setItem("ad_agent_base_url", baseUrl)
    localStorage.setItem("ad_agent_model", model)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <Card className="border-dashed">
      <button className="w-full flex items-center justify-between p-4 cursor-pointer" onClick={() => setOpen(!open)}>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Settings className="size-4" />
          <span>API 配置</span>
          <span className={`size-2 rounded-full ${hasKey ? "bg-green-500" : "bg-amber-500"}`} />
        </div>
        <span className="text-xs text-muted-foreground">{hasKey ? "已配置" : "未配置 API Key"}</span>
      </button>
      {open && (
        <CardContent className="pt-0 space-y-3">
          <div className="space-y-1.5">
            <label className="text-xs font-medium">API Key</label>
            <div className="relative">
              <input type={showKey ? "text" : "password"} value={apiKey} onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-..." className="w-full rounded-md border bg-background px-3 py-1.5 text-sm pr-9" />
              <button className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                onClick={() => setShowKey(!showKey)}>
                {showKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium">Base URL</label>
            <input type="text" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://api.deepseek.com" className="w-full rounded-md border bg-background px-3 py-1.5 text-sm" />
            <p className="text-xs text-muted-foreground">支持任何 OpenAI 兼容接口的 Base URL</p>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium">模型名称</label>
            <input type="text" value={model} onChange={(e) => setModel(e.target.value)}
              placeholder="deepseek-chat" className="w-full rounded-md border bg-background px-3 py-1.5 text-sm" />
          </div>
          <Button size="sm" onClick={handleSave} className="w-full">
            {saved ? <><Check className="size-3" /> 已保存</> : "保存配置"}
          </Button>
          <p className="text-xs text-muted-foreground">API Key 仅存储在浏览器本地。</p>
        </CardContent>
      )}
    </Card>
  )
}

// ── Input Panel ──────────────────────────────────────────────

function InputPanel({ disabled, onSubmit }: { disabled: boolean; onSubmit: (text: string, industry: string) => void }) {
  const [text, setText] = useState("")
  const [industry, setIndustry] = useState("")

  return (
    <Card className={disabled ? "opacity-60" : ""}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldCheck className="size-5 text-primary" /> 广告合规审查
        </CardTitle>
        <CardDescription>输入待审查文案，Agent 将自动执行四步审查管线。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium">审查文案</label>
            <div className="flex gap-1">
              {SAMPLE_TEXTS.map((s) => (
                <button key={s.label} onClick={() => setText(s.text)} disabled={disabled}
                  className="text-xs px-2 py-0.5 rounded-full border border-muted-foreground/20 text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors disabled:opacity-50">
                  {s.label}
                </button>
              ))}
            </div>
          </div>
          <Textarea placeholder="请粘贴或输入需要审查的广告文案……" value={text}
            onChange={(e) => setText(e.target.value)} disabled={disabled} className="min-h-32 resize-y" />
          <p className="text-xs text-muted-foreground">{text.length} 字</p>
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">所属行业</label>
          <Select value={industry} onValueChange={(v) => setIndustry(v ?? "")} disabled={disabled}>
            <SelectTrigger className="w-full"><SelectValue placeholder="选择行业分类" /></SelectTrigger>
            <SelectContent>
              {INDUSTRIES.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <Button className="w-full" size="lg" disabled={disabled || !text.trim()}
          onClick={() => onSubmit(text.trim(), industry || "general")}>
          {disabled ? <><Loader2 className="size-4 animate-spin" /> 审查中…</> : <><FileCheck className="size-4" /> 开始审查</>}
        </Button>
      </CardContent>
    </Card>
  )
}

// ── Main Page ────────────────────────────────────────────────

export default function ReviewPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [showOnboarding, setShowOnboarding] = useState(searchParams.get("onboarding") === "true")
  const [mode, setMode] = useState<"single" | "batch">("single")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ReviewResult | null>(null)
  const [animSteps, setAnimSteps] = useState<PipelineStep[]>([])
  const [error, setError] = useState<string | null>(null)
  const [needsUpgrade, setNeedsUpgrade] = useState(false)
  const [batchResults, setBatchResults] = useState<any[] | null>(null)
  const [batchSummary, setBatchSummary] = useState<any>(null)
  const timerRef = useRef<NodeJS.Timeout[]>([])

  // Animate pipeline steps during loading
  const startAnimation = useCallback(() => {
    const defaultSteps: PipelineStep[] = [
      { step: 1, name: "禁用词匹配", status: "waiting", detail: "", icon: "🔍" },
      { step: 2, name: "LLM 语境判断", status: "waiting", detail: "", icon: "🧠" },
      { step: 3, name: "RAG 法规检索", status: "waiting", detail: "", icon: "📖" },
      { step: 4, name: "替代建议生成", status: "waiting", detail: "", icon: "✏️" },
    ]
    setAnimSteps(defaultSteps)

    const delays = [200, 600, 1200, 1800]
    delays.forEach((delay, i) => {
      const t = setTimeout(() => {
        setAnimSteps(prev => prev.map((s, j) =>
          j === i ? { ...s, status: "running" as const } :
          j < i ? { ...s, status: "completed" as const } : s))
      }, delay)
      timerRef.current.push(t)
    })
  }, [])

  // Cleanup timers
  useEffect(() => {
    return () => { timerRef.current.forEach(clearTimeout) }
  }, [])

  const handleSubmit = useCallback(async (text: string, industry: string) => {
    setLoading(true)
    setError(null)
    setResult(null)
    startAnimation()

    try {
      const res = await submitReview({ text, industry: industry as any })

      // Map pipeline steps from API
      const pipelineSteps: PipelineStep[] = (res as any).pipelineSteps?.length
        ? (res as any).pipelineSteps.map((s: any) => ({
            step: s.step, name: s.name, status: s.status, detail: s.detail, icon: s.icon,
          }))
        : [
            { step: 1, name: "禁用词匹配", status: "completed", detail: `命中 ${(res as any).violations?.length || 0} 个`, icon: "🔍" },
            { step: 2, name: "LLM 语境判断", status: "completed", detail: `确认 ${res.violations?.length || 0} 个违规`, icon: "🧠" },
            { step: 3, name: "RAG 法规检索", status: res.violations?.length ? "completed" : "skipped", detail: "匹配法规条文", icon: "📖" },
            { step: 4, name: "替代建议生成", status: res.violations?.length ? "completed" : "skipped", detail: "生成合规建议", icon: "✏️" },
          ]

      // Clear animation timers
      timerRef.current.forEach(clearTimeout)
      timerRef.current = []

      setAnimSteps(pipelineSteps.map(s => ({ ...s, status: "completed" as const })))

      const violations: Violation[] = (res.violations || []).map((v: any) => ({
        id: v.id,
        word: v.text,
        type: v.category,
        law: v.lawArticle || "",
        lawContent: v.lawContent || "",
        reason: v.explanation || "",
        confidence: v.confidence ?? 0.5,
        severity: (v.severity || "medium") as RiskLevel,
        suggestion: v.suggestions?.[0]?.replacement || "需人工替换",
        relatedCases: (v.relatedCases || []).map((rc: any) => ({
          title: rc.title || "",
          penalty: rc.penalty || "",
          article: rc.article || "",
        })),
      }))

      setResult({
        reviewId: res.reviewId || "",
        riskLevel: (res as any).overallRisk as RiskLevel,
        violations,
        highlightedText: res.highlightedText,
        pipelineSteps,
        processingTimeMs: (res as any).processingTimeMs || 0,
        tokenUsage: (res as any).tokenUsage || undefined,
      })
    } catch (err: any) {
      timerRef.current.forEach(clearTimeout)
      timerRef.current = []
      if (err.status === 402) {
        setNeedsUpgrade(true)
        setError(null)
      } else {
        setError(err.message || "审查请求失败，请检查后端是否启动。")
      }
    } finally {
      setLoading(false)
    }
  }, [startAnimation])

  const handleReset = useCallback(() => {
    setResult(null)
    setError(null)
    setAnimSteps([])
  }, [])

  const riskCfg = result ? RISK_CONFIG[result.riskLevel] : null

  return (
    <main className="min-h-screen bg-background pt-20">
      <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="mb-8">
          <h1 className="text-2xl font-bold tracking-tight">审查工作台</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            广告文案合规智能审查系统 · 三层 Agent 架构
          </p>
        </header>

        <div className="space-y-6">
          <SettingsPanel />

          {/* Onboarding banner */}
          {showOnboarding && (
            <Card className="border-emerald-200 bg-gradient-to-r from-emerald-50 to-teal-50">
              <CardContent className="flex items-start gap-4 py-5">
                <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-emerald-100">
                  <ShieldCheck className="size-5 text-emerald-600" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-emerald-800">欢迎使用广告合规 AI</h3>
                  <p className="text-sm text-emerald-700 mt-1">
                    输入您的广告文案，系统将自动检测是否含有违规内容。支持单条审查和批量上传两种模式。
                  </p>
                  <div className="flex gap-2 mt-3">
                    <Button size="sm" variant="outline" className="bg-white/80" onClick={() => setShowOnboarding(false)}>
                      知道了
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Mode switcher */}
          <div className="flex items-center gap-1 rounded-lg border bg-muted/30 p-1 w-fit">
            <button
              onClick={() => { setMode("single"); setBatchResults(null); handleReset() }}
              className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors cursor-pointer
                ${mode === "single" ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"}`}
            >
              <FileCheck className="size-4" />
              单条审查
            </button>
            <button
              onClick={() => setMode("batch")}
              className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors cursor-pointer
                ${mode === "batch" ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"}`}
            >
              <Upload className="size-4" />
              批量审查
            </button>
          </div>

          {mode === "single" && (
            <>
              {/* Input (dimmed during loading) */}
              <div className={loading ? "pointer-events-none" : ""}>
                <InputPanel disabled={loading} onSubmit={handleSubmit} />
              </div>

              {/* Pipeline visualization */}
              {(loading || (result && result.pipelineSteps.length > 0)) && (
                <PipelineStepper steps={loading ? animSteps : result!.pipelineSteps} isAnimating={loading} />
              )}

              {/* Error */}
              {error && (
                <Card className="border-red-200 bg-red-50/50">
                  <CardContent className="flex items-center gap-3 py-4">
                    <AlertTriangle className="size-5 text-red-500 shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-red-700">审查失败</p>
                      <p className="text-xs text-red-600/80">{error}</p>
                    </div>
                    <Button size="sm" variant="ghost" className="ml-auto" onClick={handleReset}>
                      <RotateCcw className="size-3" /> 重试
                    </Button>
                  </CardContent>
                </Card>
              )}

              {/* Upgrade prompt */}
              {needsUpgrade && (
                <Card className="border-amber-200 bg-amber-50">
                  <CardContent className="py-6 text-center">
                    <Zap className="size-10 text-amber-500 mx-auto mb-3" />
                    <h3 className="text-lg font-semibold text-amber-800">已达使用上限</h3>
                    <p className="text-sm text-amber-700 mt-1 mb-4">当前套餐的每日审查次数已用完，升级后可继续使用。</p>
                    <div className="flex justify-center gap-3">
                      <Button onClick={() => router.push("/pricing")} className="bg-amber-600 hover:bg-amber-700">
                        <Zap className="size-4" /> 查看套餐
                      </Button>
                      <Button variant="outline" onClick={handleReset}>
                        稍后再说
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Results */}
              {result && !loading && (
            <div className="space-y-6">
              {/* High risk alert banner */}
              {result.riskLevel === "high" && (
                <div className="flex items-center gap-3 rounded-xl border-2 border-red-300 bg-red-50 p-4 shadow-lg shadow-red-100 animate-in slide-in-from-top-2">
                  <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-red-100">
                    <AlertTriangle className="size-5 text-red-600" />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-bold text-red-800">高风险警告</p>
                    <p className="text-xs text-red-700/80">检测到高风险违规内容，建议立即修改，避免违反《广告法》</p>
                  </div>
                </div>
              )}

              {/* Summary card */}
              <Card className={result.riskLevel === "pass" ? "border-emerald-200 bg-emerald-50/30" : "border-red-200 bg-red-50/30"}>
                <CardContent className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 py-5">
                  <div className="flex items-center gap-3">
                    <ShieldCheck className={`size-8 shrink-0 ${riskCfg?.color}`} />
                    <div>
                      <h2 className="text-lg font-semibold">审查结果</h2>
                      <p className="text-sm text-muted-foreground">
                        {result.violations.length === 0
                          ? "未检测到违规内容"
                          : `共检测到 ${result.violations.length} 处违规`}
                        {result.processingTimeMs > 0 && ` · ${result.processingTimeMs}ms`}
                        {result.tokenUsage && result.tokenUsage.totalTokens
                          ? ` · ${result.tokenUsage.totalTokens} tokens`
                          : ""}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button size="sm" variant="outline" onClick={() => exportSingleReview(result)}>
                      <Download className="size-3.5" /> 导出
                    </Button>
                    <Badge className={`text-base px-4 py-1.5 ${riskCfg?.className}`}>
                      {riskCfg?.label}
                    </Badge>
                  </div>
                </CardContent>
              </Card>

              {/* Highlighted text */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">高亮文本</CardTitle>
                  <CardDescription>标记处为检测到的违规内容</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-sm leading-relaxed whitespace-pre-wrap"
                    dangerouslySetInnerHTML={{ __html: sanitizeHtml(result.highlightedText) }} />
                </CardContent>
              </Card>

              {/* Violation cards */}
              {result.violations.length > 0 && (
                <div className="space-y-4">
                  <h3 className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                    <AlertTriangle className="size-4" />
                    违规明细 · {result.violations.length} 项
                  </h3>
                    <div className="grid gap-4">
                    {result.violations.map((v) => <ViolationCard key={v.id} violation={v} reviewId={result.reviewId} />)}
                  </div>
                </div>
              )}

              {/* Reset button */}
              <div className="flex justify-center">
                <Button onClick={handleReset} variant="outline">
                  <RotateCcw className="size-4" /> 开始新审查
                </Button>
              </div>
            </div>
          )}
            </>

          )}

          {mode === "batch" && (
            <>
              {!batchResults ? (
                <BatchUpload onResults={(results) => {
                  const summary = { high: 0, medium: 0, low: 0, pass: 0, error: 0 }
                  for (const r of results) {
                    const k = r.overall_risk
                    if (k in summary) summary[k as keyof typeof summary]++
                    else summary.error++
                  }
                  setBatchResults(results)
                  setBatchSummary(summary)
                }} />
              ) : (
                <BatchResultList
                  results={batchResults}
                  summary={batchSummary || { high: 0, medium: 0, low: 0, pass: 0, error: 0 }}
                  onReset={() => { setBatchResults(null); setBatchSummary(null) }}
                />
              )}
            </>
          )}
        </div>
      </div>
    </main>
  )
}
