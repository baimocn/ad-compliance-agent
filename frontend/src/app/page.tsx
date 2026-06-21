"use client"

import { useState, useCallback, useEffect, useRef } from "react"
import {
  ShieldCheck, Zap, Brain, BookOpen, Wand2,
  Check, Loader2, AlertTriangle, FileCheck,
  ArrowRight, Sparkles, ChevronRight,
} from "lucide-react"
import { Textarea } from "@/components/ui/textarea"
import { submitReview } from "@/lib/api"
import { useScrollReveal, useCountUp } from "@/hooks/use-scroll-reveal"

const SAMPLE_TEXTS = [
  { text: "全网最低价，买到就是赚到！", label: "极限用语", severity: "high" },
  { text: "100%有效，根治痘痘，永不反弹", label: "虚假宣传", severity: "high" },
  { text: "本产品采用90%白鹅绒填充，蓬松度700+", label: "正常描述", severity: "pass" },
  { text: "国家级产品，世界领先技术", label: "夸大宣传", severity: "medium" },
]

const PLATFORMS = [
  "抖音", "小红书", "微信公众号", "淘宝", "天猫",
  "京东", "拼多多", "快手", "微博", "B站",
]

const MARQUEE_KEYWORDS = [
  "规则引擎", "AI 语义分析", "RAG 检索", "合规审查", "广告法",
  "禁用词检测", "替代建议", "批量审查", "风险评估", "法规匹配",
  "实时检测", "DeepSeek", "智能判断", "文案优化", "秒级响应", "零成本",
]

const CAPABILITIES = [
  {
    icon: Zap,
    num: "01",
    title: "规则引擎",
    desc: "288 条禁用词正则匹配",
    detail: "毫秒级响应，零 LLM 成本，覆盖极限用语、虚假宣传等全部类别",
    gradient: "from-amber-400 to-orange-400",
    iconBg: "bg-amber-50",
    iconColor: "text-amber-500",
  },
  {
    icon: Brain,
    num: "02",
    title: "LLM 语境判断",
    desc: "DeepSeek 智能语义分析",
    detail: "区分违规营销 vs 客观参数描述，理解语境含义",
    gradient: "from-blue-400 to-cyan-400",
    iconBg: "bg-blue-50",
    iconColor: "text-blue-500",
  },
  {
    icon: BookOpen,
    num: "03",
    title: "RAG 法规检索",
    desc: "110 条法规 + 50 条案例",
    detail: "四维融合检索，精准匹配法条依据",
    gradient: "from-violet-400 to-purple-400",
    iconBg: "bg-violet-50",
    iconColor: "text-violet-500",
  },
]

const VIOLATION_EXAMPLES = [
  { original: "全网最低价", fixed: "限时特惠价", category: "极限用语", law: "广告法第九条" },
  { original: "根治一切失眠", fixed: "辅助改善睡眠", category: "虚假宣传", law: "广告法第二十八条" },
  { original: "国家级新产品", fixed: "高品质产品", category: "虚假荣誉", law: "广告法第十一条" },
  { original: "100%纯天然", fixed: "天然成分", category: "绝对化用语", law: "广告法第八条" },
]

const SEVERITY_MAP: Record<string, { color: string; bgClass: string; label: string }> = {
  high: { color: "text-red-500", bgClass: "bg-red-50 text-red-600 border-red-100", label: "高风险" },
  medium: { color: "text-amber-500", bgClass: "bg-amber-50 text-amber-600 border-amber-100", label: "中风险" },
  low: { color: "text-emerald-500", bgClass: "bg-emerald-50 text-emerald-600 border-emerald-100", label: "低风险" },
  pass: { color: "text-gray-400", bgClass: "bg-gray-50 text-gray-500 border-gray-100", label: "合规" },
}

export default function Home() {
  const [text, setText] = useState("")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeStep, setActiveStep] = useState(0)


  const marqueeRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = marqueeRef.current
    if (!el) return
    let offset = 0
    let paused = false
    const speed = 0.5
    let rafId: number
    const half = el.scrollWidth / 2
    const animate = () => {
      if (!paused) {
        offset -= speed
        if (offset <= -half) offset = 0
        el.style.transform = `translateX(${offset}px)`
      }
      rafId = requestAnimationFrame(animate)
    }
    rafId = requestAnimationFrame(animate)
    const pause = () => { paused = true }
    const resume = () => { paused = false }
    el.parentElement?.addEventListener("mouseenter", pause)
    el.parentElement?.addEventListener("mouseleave", resume)
    return () => {
      cancelAnimationFrame(rafId)
      el.parentElement?.removeEventListener("mouseenter", pause)
      el.parentElement?.removeEventListener("mouseleave", resume)
    }
  }, [])

  const handleSubmit = useCallback(async () => {
    if (!text.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await submitReview({ text: text.trim(), industry: "general" as any })
      const violations = (res.violations || []).map((v: any) => ({
        word: v.text,
        type: v.category,
        severity: v.severity,
        reason: v.explanation || "",
        suggestion: v.suggestions?.[0]?.replacement || "",
      }))
      setResult({
        riskLevel: res.overallRisk,
        violations,
        time: res.processingTimeMs || 0,
      })
    } catch (err: any) {
      setError(err.message || "审查失败，请确认后端已启动")
    } finally {
      setLoading(false)
    }
  }, [text])

  const riskInfo = result ? SEVERITY_MAP[result.riskLevel] || SEVERITY_MAP.low : null

  return (
    <div className="min-h-screen bg-white">

      {/* ═══════════════════════════════════════════════════
          Block 1 — Hero (White, Apple-style)
          ═══════════════════════════════════════════════════ */}
      <section className="relative min-h-[90vh] flex items-center bg-white overflow-hidden">
        {/* Decorative light orbs */}
        <div className="absolute top-32 right-[10%] w-[600px] h-[600px] rounded-full bg-blue-100/40 blur-[120px] animate-hero-bloom" />
        <div className="absolute bottom-20 left-[5%] w-[400px] h-[400px] rounded-full bg-violet-100/30 blur-[100px] animate-float" />

        <div className="relative z-10 max-w-5xl mx-auto px-6 w-full py-20">
          {/* Status badge */}
          <div className="inline-flex items-center gap-2.5 rounded-full border border-gray-200 bg-gray-50 px-4 py-1.5 mb-10 animate-fade-in">
            <span className="size-2 rounded-full bg-emerald-400 animate-pulse-dot" />
            <span className="text-xs font-medium text-gray-500">
              三级 Agent 架构 · 秒级响应
            </span>
          </div>

          {/* Title — large serif accent */}
          <h1 className="text-[3.2rem] sm:text-[4.5rem] lg:text-[5.5rem] font-bold tracking-tight leading-[1.05] mb-8 animate-slide-up" style={{ letterSpacing: '-0.03em' }}>
            <span className="text-[#0a0a0a]">智能广告合规</span>
            <br />
            <span className="bg-gradient-to-r from-[#0066ff] to-blue-400 bg-clip-text text-transparent animate-gradient">
              一秒洞察风险
            </span>
          </h1>

          <p className="text-lg sm:text-xl text-gray-500 max-w-2xl mb-10 leading-relaxed animate-slide-up" style={{ animationDelay: '0.1s' }}>
            288 条规则引擎 × LLM 语境判断 × RAG 法规检索
            <br className="hidden sm:block" />
            <span className="text-gray-400">一次罚款 20 万，我们帮你提前规避</span>
          </p>

          {/* Action buttons */}
          <div className="flex flex-wrap items-center gap-4 mb-16 animate-slide-up" style={{ animationDelay: '0.2s' }}>
            <button
              onClick={() => document.getElementById('quick-review')?.scrollIntoView({ behavior: 'smooth' })}
              className="btn-primary bg-[#0a0a0a] text-white rounded-full px-8 py-3.5 font-medium text-sm flex items-center gap-2 cursor-pointer"
            >
              开始审查 <ArrowRight className="size-4" />
            </button>
            <button
              onClick={() => document.getElementById('capabilities')?.scrollIntoView({ behavior: 'smooth' })}
              className="btn-ghost rounded-full px-8 py-3.5 font-medium text-sm text-gray-600 border border-gray-200 flex items-center gap-2 cursor-pointer"
            >
              了解更多
            </button>
          </div>

          {/* Trust badges */}
          <div className="flex items-center gap-5 text-gray-300 text-xs animate-slide-up" style={{ animationDelay: '0.3s' }}>
            <div className="flex items-center gap-1.5">
              <ShieldCheck className="size-3.5" />
              <span>覆盖 110+ 法规</span>
            </div>
            <div className="w-px h-3 bg-gray-200" />
            <div className="flex items-center gap-1.5">
              <Zap className="size-3.5" />
              <span>10 秒出结果</span>
            </div>
            <div className="w-px h-3 bg-gray-200" />
            <div className="flex items-center gap-1.5">
              <Brain className="size-3.5" />
              <span>AI 语义分析</span>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════
          Block 2 — Marquee (Keywords)
          ═══════════════════════════════════════════════════ */}
      <div className="bg-gray-50 border-y border-gray-100 py-5 overflow-hidden">
        <div ref={marqueeRef} className="marquee-track" style={{ animation: "none", transform: "translateX(0)" }}>
          {[...MARQUEE_KEYWORDS, ...MARQUEE_KEYWORDS].map((kw, i) => (
            <span key={i} className="flex items-center gap-4 px-4 text-sm text-gray-400 whitespace-nowrap select-none">
              {kw}
              <span className="size-1 rounded-full bg-gray-300 shrink-0" />
            </span>
          ))}
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════
          Block 3 - Quick Review (Embedded)
          ═══════════════════════════════════════════════════ */}
      <SectionReveal>
        <section id="quick-review" className="bg-white py-24 sm:py-32">
          <div className="max-w-3xl mx-auto px-6">
            <div className="text-center mb-12">
              <span className="inline-block text-xs font-semibold text-[#0066ff] tracking-widest uppercase mb-3">
                Quick Start
              </span>
              <h2 className="text-2xl sm:text-3xl font-bold text-[#0a0a0a]">
                输入文案，即刻审查
              </h2>
            </div>

            <div className="rounded-[28px] border border-gray-200 bg-white p-6 sm:p-8 shadow-[0_4px_40px_-12px_rgba(0,0,0,0.06)]">
              <Textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="粘贴你的广告文案..."
                className="min-h-[110px] resize-none bg-gray-50 border-gray-200 text-[#0a0a0a] placeholder:text-gray-300 rounded-2xl focus-visible:ring-[#0066ff]/20 focus-visible:border-[#0066ff]/30 text-sm"
              />

              <div className="flex items-center justify-between mt-4">
                <div className="flex gap-2">
                  {SAMPLE_TEXTS.slice(0, 3).map((s, i) => (
                    <button
                      key={i}
                      onClick={() => setText(s.text)}
                      className="text-[11px] px-3 py-1.5 rounded-full bg-gray-50 border border-gray-200 text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-all cursor-pointer"
                    >
                      {s.label}
                    </button>
                  ))}
                </div>

                <button
                  onClick={handleSubmit}
                  disabled={loading || !text.trim()}
                  className="btn-primary bg-[#0a0a0a] text-white rounded-full px-6 py-2.5 font-medium text-sm flex items-center gap-2 disabled:opacity-30 disabled:pointer-events-none cursor-pointer"
                >
                  {loading ? (
                    <>
                      <Loader2 className="size-4 animate-spin" /> 审查中…
                    </>
                  ) : (
                    <>
                      <FileCheck className="size-4" /> 开始审查
                    </>
                  )}
                </button>
              </div>

              {result && (
                <div className="mt-5 pt-5 border-t border-gray-100 animate-fade-in">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {riskInfo && (
                        <span className={`text-xs font-semibold px-3 py-1 rounded-full border ${riskInfo.bgClass}`}>
                          {riskInfo.label}
                        </span>
                      )}
                      <span className="text-xs text-gray-400">
                        {result.violations.length} 处违规 · {result.time}ms
                      </span>
                    </div>
                    <a href="/review" className="text-xs text-[#0066ff] hover:underline flex items-center gap-1 transition-colors">
                      完整报告 <ChevronRight className="size-3" />
                    </a>
                  </div>
                </div>
              )}

              {error && (
                <div className="mt-3 flex items-center gap-2 text-red-500 text-xs">
                  <AlertTriangle className="size-3" />
                  <span>{error}</span>
                </div>
              )}
            </div>
          </div>
        </section>
      </SectionReveal>

      {/* ═══════════════════════════════════════════════════
          Block 4 — Capabilities (Bento Grid Style)
          ═══════════════════════════════════════════════════ */}
      <SectionReveal>
        <section id="capabilities" className="bg-gray-50 py-24 sm:py-32">
          <div className="max-w-5xl mx-auto px-6">
            <div className="text-center mb-16">
              <span className="inline-block text-xs font-semibold text-[#0066ff] tracking-widest uppercase mb-3">
                三级审查引擎
              </span>
              <h2 className="text-2xl sm:text-4xl font-bold text-[#0a0a0a]">
                从规则到智能，逐层深入
              </h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
              {CAPABILITIES.map((step, i) => {
                const Icon = step.icon
                const isActive = activeStep === i
                return (
                  <div
                    key={i}
                    className={`card-3d rounded-[28px] bg-white p-8 cursor-pointer border transition-all duration-500 ${
                      isActive ? 'border-[#0066ff]/20 shadow-[0_20px_60px_-15px_rgba(0,102,255,0.1)]' : 'border-gray-200'
                    }`}
                    onMouseEnter={() => setActiveStep(i)}
                  >
                    <div className="flex items-center justify-between mb-6">
                      <div className={`size-14 rounded-2xl ${step.iconBg} flex items-center justify-center`}>
                        <Icon className={`size-6 ${step.iconColor}`} />
                      </div>
                      <span className="text-4xl font-bold text-gray-100 select-none">{step.num}</span>
                    </div>
                    <h3 className="text-lg font-bold text-[#0a0a0a] mb-2">{step.title}</h3>
                    <p className="text-sm text-gray-500 leading-relaxed mb-3">{step.desc}</p>
                    <p className={`text-xs text-gray-400 overflow-hidden transition-all duration-500 ${
                      isActive ? 'max-h-12 opacity-100' : 'max-h-0 opacity-0'
                    }`}>
                      {step.detail}
                    </p>
                  </div>
                )
              })}
            </div>
          </div>
        </section>
      </SectionReveal>

      {/* ═══════════════════════════════════════════════════
          Block 5 — Stats (Dark, 4 columns)
          ═══════════════════════════════════════════════════ */}
      <SectionReveal>
        <section className="bg-white py-20 sm:py-24 border-y border-gray-100">
          <div className="max-w-5xl mx-auto px-6">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-8">
              {[
                { value: 288, suffix: "+", label: "禁用词规则" },
                { value: 110, suffix: "+", label: "法规数据库" },
                { value: 50, suffix: "+", label: "典型案例" },
                { value: 10, suffix: "s", label: "平均审查时间" },
              ].map((stat, i) => (
                <StatNumber key={i} value={stat.value} suffix={stat.suffix} label={stat.label} />
              ))}
            </div>
          </div>
        </section>
      </SectionReveal>

      {/* ═══════════════════════════════════════════════════
          Block 6 — Violation Examples
          ═══════════════════════════════════════════════════ */}
      <SectionReveal>
        <section className="bg-white py-24 sm:py-32">
          <div className="max-w-4xl mx-auto px-6">
            <div className="text-center mb-14">
              <span className="inline-block text-xs font-semibold text-[#0066ff] tracking-widest uppercase mb-3">
                Detection Examples
              </span>
              <h2 className="text-2xl sm:text-3xl font-bold text-[#0a0a0a]">
                这些违规文案，我们都能识别
              </h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              {VIOLATION_EXAMPLES.map((ex, i) => (
                <div key={i} className="card-3d rounded-[28px] bg-white border border-gray-200 p-6 hover:shadow-[0_20px_60px_-15px_rgba(0,0,0,0.06)] transition-all">
                  <div className="flex items-center gap-2 mb-5">
                    <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-red-50 text-red-500 border border-red-100">
                      {ex.category}
                    </span>
                    <span className="text-[11px] text-gray-400">{ex.law}</span>
                  </div>
                  <div className="space-y-3">
                    <div className="flex items-start gap-2.5">
                      <span className="shrink-0 size-5 rounded-full bg-red-50 flex items-center justify-center mt-0.5">
                        <AlertTriangle className="size-3 text-red-400" />
                      </span>
                      <span className="text-sm text-red-400 line-through decoration-red-200">
                        {ex.original}
                      </span>
                    </div>
                    <div className="flex items-start gap-2.5">
                      <span className="shrink-0 size-5 rounded-full bg-emerald-50 flex items-center justify-center mt-0.5">
                        <Check className="size-3 text-emerald-500" />
                      </span>
                      <span className="text-sm text-emerald-600 font-medium">
                        {ex.fixed}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </SectionReveal>

      {/* ═══════════════════════════════════════════════════
          Block 7 — Testimonials
          ═══════════════════════════════════════════════════ */}
      <SectionReveal>
        <section className="bg-gray-50 py-24 sm:py-32">
          <div className="max-w-4xl mx-auto px-6">
            <div className="text-center mb-14">
              <span className="inline-block text-xs font-semibold text-[#0066ff] tracking-widest uppercase mb-3">
                用户反馈
              </span>
              <h2 className="text-2xl sm:text-3xl font-bold text-[#0a0a0a]">
                他们已经在用
              </h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              {[
                {
                  quote: "之前每次发广告都要人工查一遍广告法，现在 10 秒就出结果，省了大量时间。",
                  initial: "电",
                  name: "电商运营",
                  role: "某头部美妆品牌",
                  gradient: "from-[#0066ff] to-blue-500",
                },
                {
                  quote: "批量审查功能太好用了，一次上传 100 条文案，几分钟全部搞定，还能导出报告。",
                  initial: "自",
                  name: "自媒体创作者",
                  role: "小红书博主",
                  gradient: "from-violet-500 to-purple-500",
                },
              ].map((t, i) => (
                <div key={i} className="card-3d rounded-[28px] bg-white border border-gray-200 p-7">
                  <div className="text-gray-200 text-4xl font-serif leading-none mb-4">&ldquo;</div>
                  <p className="text-sm text-gray-600 leading-relaxed mb-6">
                    {t.quote}
                  </p>
                  <div className="flex items-center gap-3">
                    <div className={`size-9 rounded-full bg-gradient-to-br ${t.gradient} flex items-center justify-center text-xs font-bold text-white`}>
                      {t.initial}
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-[#0a0a0a]">{t.name}</p>
                      <p className="text-xs text-gray-400">{t.role}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </SectionReveal>

      {/* ═══════════════════════════════════════════════════
          Block 8 — Footer
          ═══════════════════════════════════════════════════ */}
      <footer className="bg-[#0a0a0a] py-10">
        <div className="max-w-5xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="size-7 rounded-lg bg-gradient-to-br from-[#0066ff] to-blue-400 flex items-center justify-center">
              <ShieldCheck className="size-3.5 text-white" />
            </div>
            <span className="text-sm font-bold text-white/70">合规 AI</span>
          </div>
          <p className="text-xs text-white/25">
            Agent Hackathon 参赛作品 · 仅供学习和评审使用
          </p>
        </div>
      </footer>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════
   Section wrapper with scroll reveal
   ═══════════════════════════════════════════════════════ */
function SectionReveal({ children }: { children: React.ReactNode }) {
  const { ref, visible } = useScrollReveal(0.1)
  return (
    <div ref={ref} className={`scroll-reveal-scale ${visible ? "revealed" : ""}`}>
      {children}
    </div>
  )
}

/* ═══════════════════════════════════════════════════════
   Animated stat number
   ═══════════════════════════════════════════════════════ */
function StatNumber({ value, suffix, label }: { value: number; suffix: string; label: string }) {
  const { ref, count } = useCountUp(value)
  return (
    <div ref={ref} className="text-center">
      <div className="text-3xl sm:text-4xl font-bold text-[#0a0a0a] mb-1 font-mono tracking-tight">
        {count}<span className="text-[#0066ff]">{suffix}</span>
      </div>
      <div className="text-xs text-gray-400">{label}</div>
    </div>
  )
}
