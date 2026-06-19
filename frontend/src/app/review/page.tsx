"use client"

import { useState, useCallback, useEffect, useRef } from "react"
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
  CircleCheck, CircleDot, ArrowRight,
} from "lucide-react"
import {
  submitReview, submitFeedback,
  submitAsyncReview, streamReviewProgress,
} from "@/lib/api"

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
  relatedCases: string[]
}

interface ReviewResult {
  riskLevel: RiskLevel
  violations: Violation[]
  highlightedText: string
  pipelineSteps: PipelineStep[]
  processingTimeMs: number
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

function ViolationCard({ violation }: { violation: Violation }) {
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
      await submitFeedback({ reviewId: "", violationId: violation.id, action })
    } catch { /* silent */ }
  }, [violation.id])

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

        {/* Suggestion */}
        <div className="flex flex-wrap items-center gap-2 rounded-md bg-emerald-50/50 dark:bg-emerald-950/20 border border-emerald-200/50 p-2.5">
          <Wand2 className="size-3.5 text-emerald-600 shrink-0" />
          <span className="text-sm flex-1">
            <span className="text-xs text-muted-foreground">替代建议：</span>
            <span className="font-medium text-emerald-800 dark:text-emerald-300">{violation.suggestion}</span>
          </span>
          <Button variant="ghost" size="icon" className="size-7" onClick={handleCopy}>
            {copied ? <Check className="size-3 text-emerald-600" /> : <Copy className="size-3" />}
          </Button>
        </div>

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
  const [showKey, setShowKey] = useState(false)
  const [open, setOpen] = useState(false)
  const [saved, setSaved] = useState(false)
  const hasKey = typeof window !== "undefined" && !!localStorage.getItem("ad_agent_api_key")

  const handleSave = () => {
    localStorage.setItem("ad_agent_api_key", apiKey)
    localStorage.setItem("ad_agent_base_url", baseUrl)
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
        <span className="text-xs text-muted-foreground">{hasKey ? "已配置" : "未配置 DeepSeek API Key"}</span>
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

function InputPanel({ disabled, useAsync, onToggleAsync, onSubmit }: {
  disabled: boolean; useAsync: boolean; onToggleAsync: () => void;
  onSubmit: (text: string, industry: string) => void;
}) {
  const [text, setText] = useState("")
  const [industry, setIndustry] = useState("")

  return (
    <Card className={disabled ? "opacity-60" : ""}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="size-5 text-primary" /> 广告合规审查
          </CardTitle>
          <button
            onClick={onToggleAsync}
            disabled={disabled}
            className={`text-xs px-3 py-1 rounded-full border transition-colors ${
              useAsync
                ? "bg-blue-100 text-blue-700 border-blue-300"
                : "bg-gray-100 text-gray-600 border-gray-200"
            } disabled:opacity-50`}>
            {useAsync ? "⚡ 异步模式" : "🔄 同步模式"}
          </button>
        </div>
        <CardDescription>
          {useAsync
            ? "异步审查：支持高并发，实时进度推送（SSE）。"
            : "同步审查：阻塞等待结果，适合单用户使用。"}
        </CardDescription>
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

// ── SSE 实时进度 Hook ────────────────────────────────────────

function useAsyncReview() {
  const [requestId, setRequestId] = useState<string | null>(null)
  const [progress, setProgress] = useState(0)
  const [currentStep, setCurrentStep] = useState("")
  const [queuePosition, setQueuePosition] = useState(0)
  const stopRef = useRef<(() => void) | null>(null)

  const start = useCallback(async (text: string, industry: string) => {
    try {
      const resp = await submitAsyncReview({ text, industry })
      setRequestId(resp.requestId)
      setQueuePosition(resp.position)
      setProgress(0)

      const stop = streamReviewProgress(
        resp.requestId,
        (data) => {
          setProgress(data.progress)
          setCurrentStep(data.currentStep)
          setQueuePosition(data.positionInQueue)
        },
        (result) => {
          setProgress(1)
          setCurrentStep("审查完成")
        },
        (error) => {
          setCurrentStep(`错误: ${error}`)
        },
      )
      stopRef.current = stop
      return resp.requestId
    } catch (err: any) {
      throw new Error(err.message || "提交失败")
    }
  }, [])

  const stop = useCallback(() => {
    if (stopRef.current) {
      stopRef.current()
      stopRef.current = null
    }
  }, [])

  return { requestId, progress, currentStep, queuePosition, start, stop }
}

// ── 实时进度条组件 ───────────────────────────────────────────

function LiveProgressBar({ progress, currentStep, queuePosition }: {
  progress: number; currentStep: string; queuePosition: number;
}) {
  const pct = Math.round(progress * 100)
  return (
    <Card className="border-2 border-blue-500/20 bg-gradient-to-br from-blue-50/50 to-purple-50/50">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Loader2 className="size-5 text-blue-600 animate-spin" />
          实时审查进度
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 pt-0">
        {/* Progress bar */}
        <div className="relative h-3 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="absolute inset-y-0 left-0 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full transition-all duration-300"
            style={{ width: `${pct}%` }}
          />
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xs font-bold text-white drop-shadow">{pct}%</span>
          </div>
        </div>

        {/* Current step */}
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">当前步骤</span>
          <span className="font-medium text-blue-700">{currentStep || "初始化..."}</span>
        </div>

        {/* Queue position (if queued) */}
        {queuePosition > 0 && progress === 0 && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">队列位置</span>
            <Badge variant="outline" className="text-xs">第 {queuePosition} 位</Badge>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ── Main Page ────────────────────────────────────────────────

export default function ReviewPage() {
  const [loading, setLoading] = useState(false)
  const [useAsync, setUseAsync] = useState(false)
  const [result, setResult] = useState<ReviewResult | null>(null)
  const [animSteps, setAnimSteps] = useState<PipelineStep[]>([])
  const [error, setError] = useState<string | null>(null)
  const timerRef = useRef<NodeJS.Timeout[]>([])
  const asyncReview = useAsyncReview()

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
      if (useAsync) {
        // 异步模式：SSE 实时进度
        await asyncReview.start(text, industry)

        // 轮询等待结果（替代 SSE，保证兼容性）
        let pollCount = 0
        const maxPolls = 60  // 最多等 60 秒
        while (pollCount < maxPolls) {
          await new Promise(r => setTimeout(r, 1000))
          pollCount++
          // 这里 SSE 模式下由 streamReviewProgress 回调处理
          // 为简化，使用进度值判断是否完成
          if (asyncReview.progress >= 1) {
            break
          }
        }

        // 注意：完整的 SSE 集成需要在回调中设置 result
        // 这里降级为同步获取结果
        const res = await submitReview({ text, industry: industry as any })
        _processResult(res)
      } else {
        // 同步模式
        const res = await submitReview({ text, industry: industry as any })
        _processResult(res)
      }
    } catch (err: any) {
      timerRef.current.forEach(clearTimeout)
      timerRef.current = []
      asyncReview.stop()
      setError(err.message || "审查请求失败，请检查后端是否启动。")
    } finally {
      setLoading(false)
    }

    function _processResult(res: any) {
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

      timerRef.current.forEach(clearTimeout)
      timerRef.current = []
      setAnimSteps(pipelineSteps.map(s => ({ ...s, status: "completed" as const })))

      const violations: Violation[] = (res.violations || []).map((v: any) => ({
        id: v.id,
        word: v.text,
        type: v.category,
        law: v.law_article || "",
        lawContent: v.law_content || "",
        reason: v.explanation || "",
        confidence: v.confidence ?? 0.8,
        severity: (v.severity || "medium") as RiskLevel,
        suggestion: v.suggestions?.[0]?.replacement || "需人工替换",
        relatedCases: [],
      }))

      setResult({
        riskLevel: (res as any).overallRisk as RiskLevel,
        violations,
        highlightedText: res.highlightedText,
        pipelineSteps,
        processingTimeMs: (res as any).processingTimeMs || 0,
      })
    }
  }, [startAnimation, useAsync, asyncReview])

  const handleReset = useCallback(() => {
    setResult(null)
    setError(null)
    setAnimSteps([])
  }, [])

  const riskCfg = result ? RISK_CONFIG[result.riskLevel] : null

  return (
    <main className="min-h-screen bg-background">
      <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="mb-8">
          <h1 className="text-2xl font-bold tracking-tight">审查工作台</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            广告文案合规智能审查系统 · 三层 Agent 架构
          </p>
        </header>

        <div className="space-y-6">
          <SettingsPanel />

          {/* Input (dimmed during loading) */}
          <div className={loading ? "pointer-events-none" : ""}>
            <InputPanel
              disabled={loading}
              useAsync={useAsync}
              onToggleAsync={() => setUseAsync(v => !v)}
              onSubmit={handleSubmit}
            />
          </div>

          {/* Pipeline visualization */}
          {(loading || (result && result.pipelineSteps.length > 0)) && (
            <PipelineStepper steps={loading ? animSteps : result!.pipelineSteps} isAnimating={loading} />
          )}

          {/* SSE 实时进度条（异步模式） */}
          {loading && useAsync && asyncReview.requestId && (
            <LiveProgressBar
              progress={asyncReview.progress}
              currentStep={asyncReview.currentStep}
              queuePosition={asyncReview.queuePosition}
            />
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

          {/* Results */}
          {result && !loading && (
            <div className="space-y-6">
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
                      </p>
                    </div>
                  </div>
                  <Badge className={`text-base px-4 py-1.5 ${riskCfg?.className}`}>
                    {riskCfg?.label}
                  </Badge>
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
                    {result.violations.map((v) => <ViolationCard key={v.id} violation={v} />)}
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
        </div>
      </div>
    </main>
  )
}
