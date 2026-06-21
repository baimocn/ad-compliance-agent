"use client"

import { useEffect, useState, useCallback } from "react"
import { useRouter } from "next/navigation"
import { History, Loader2, AlertCircle, FileSearch, ShieldCheck, Search, X } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth"
import { getMyReviews } from "@/lib/api"

interface ReviewItem {
  review_id: string
  text_preview: string
  status: string
  overall_risk: string
  violation_count: number
  created_at: string
}

const RISK_OPTIONS = [
  { value: "all", label: "全部风险" },
  { value: "high", label: "高风险" },
  { value: "medium", label: "中风险" },
  { value: "low", label: "低风险" },
  { value: "pass", label: "通过" },
]

const RISK_BADGE: Record<string, string> = {
  high: "bg-red-100 text-red-800 border-red-300",
  medium: "bg-amber-100 text-amber-800 border-amber-300",
  low: "bg-green-100 text-green-800 border-green-300",
  pass: "bg-gray-100 text-gray-700 border-gray-300",
}

const RISK_LABEL: Record<string, string> = {
  high: "高风险",
  medium: "中风险",
  low: "低风险",
  pass: "通过",
}

export default function HistoryPage() {
  const { isAuthenticated, loading: authLoading } = useAuth()
  const router = useRouter()
  const [reviews, setReviews] = useState<ReviewItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [riskFilter, setRiskFilter] = useState("all")
  const [searchQuery, setSearchQuery] = useState("")
  const [pendingSearch, setPendingSearch] = useState("")
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")

  const doFetch = useCallback(async (risk: string, query: string, from: string, to: string) => {
    setLoading(true)
    setError(null)
    try {
      const data = await getMyReviews(50, risk, query || undefined, from || undefined, to || undefined)
      setReviews(data.reviews || [])
    } catch (err: any) {
      setError(err.message || "获取历史记录失败")
    } finally {
      setLoading(false)
    }
  }, [])

  const applyFilters = useCallback(() => {
    setSearchQuery(pendingSearch)
    doFetch(riskFilter, pendingSearch, dateFrom, dateTo)
  }, [pendingSearch, riskFilter, dateFrom, dateTo, doFetch])

  useEffect(() => {
    if (authLoading) return
    if (!isAuthenticated) { router.push("/login"); return }
    doFetch(riskFilter, "", dateFrom, dateTo)
  }, [authLoading, isAuthenticated, router, riskFilter, dateFrom, dateTo, doFetch])

  const inputClass = "w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"

  return (
    <main className="min-h-[calc(100vh-3.5rem)] bg-background">
      <div className="mx-auto max-w-4xl px-4 pt-24 pb-8 sm:px-6 lg:px-8 space-y-6">
        <header>
          <h1 className="text-[22px] font-bold tracking-tight text-[#0a0a0a] flex items-center gap-2">
            <History className="size-6 text-[#0066ff]" />
            审查历史
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">查看所有历史审查记录</p>
        </header>

        {/* Filters */}
        <Card>
          <CardContent className="flex flex-wrap items-end gap-3 py-4">
            <div className="flex-1 min-w-[160px]">
              <label className="text-xs font-medium text-muted-foreground mb-1 block">搜索文案</label>
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
                <input
                  type="text"
                  value={pendingSearch}
                  onChange={e => setPendingSearch(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && applyFilters()}
                  placeholder="关键词…"
                  className={`${inputClass} pl-8`}
                />
                {pendingSearch && (
                  <button onClick={() => { setPendingSearch(""); setSearchQuery(""); }} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                    <X className="size-3.5" />
                  </button>
                )}
              </div>
            </div>
            <div className="w-[130px]">
              <label className="text-xs font-medium text-muted-foreground mb-1 block">风险等级</label>
              <select value={riskFilter} onChange={e => setRiskFilter(e.target.value)} className={inputClass}>
                {RISK_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div className="w-[140px]">
              <label className="text-xs font-medium text-muted-foreground mb-1 block">开始日期</label>
              <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className={inputClass} />
            </div>
            <div className="w-[140px]">
              <label className="text-xs font-medium text-muted-foreground mb-1 block">结束日期</label>
              <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className={inputClass} />
            </div>
            <Button size="sm" onClick={applyFilters} className="shrink-0">筛选</Button>
          </CardContent>
        </Card>

        {authLoading || (loading && reviews.length === 0) ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <Card className="border-red-200 bg-red-50/50">
            <CardContent className="flex items-center gap-3 py-4">
              <AlertCircle className="size-5 text-red-500 shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-medium text-red-700">{error}</p>
              </div>
              <Button size="sm" variant="ghost" onClick={() => doFetch(riskFilter, searchQuery, dateFrom, dateTo)}>重试</Button>
            </CardContent>
          </Card>
        ) : reviews.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center gap-3 py-12">
              <FileSearch className="size-10 text-muted-foreground/50" />
              <div className="text-center">
                <p className="text-sm font-medium text-muted-foreground">暂无匹配记录</p>
                <p className="text-xs text-muted-foreground/70 mt-1">
                  {riskFilter !== "all" || searchQuery || dateFrom || dateTo ? "尝试调整筛选条件" : "提交一条文案审查后，记录会出现在这里"}
                </p>
              </div>
              <Button variant="outline" size="sm" onClick={() => router.push("/review")}>去审查</Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {loading && <div className="flex justify-center py-4"><Loader2 className="size-5 animate-spin text-muted-foreground" /></div>}
            {reviews.map((r) => (
              <Card key={r.review_id} className="hover:border-muted-foreground/20 transition-colors">
                <CardContent className="flex items-center gap-4 py-4">
                  <ShieldCheck className={`size-6 shrink-0 ${
                    r.overall_risk === "high" ? "text-red-500" :
                    r.overall_risk === "medium" ? "text-amber-500" :
                    r.overall_risk === "low" ? "text-green-500" : "text-gray-400"
                  }`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{r.text_preview}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {r.created_at?.replace("T", " ").slice(0, 19)}
                    </p>
                  </div>
                  <Badge variant="outline" className={`text-xs shrink-0 ${RISK_BADGE[r.overall_risk] || ""}`}>
                    {RISK_LABEL[r.overall_risk] || r.overall_risk}
                  </Badge>
                  <span className="text-xs text-muted-foreground tabular-nums shrink-0">
                    {r.violation_count} 项违规
                  </span>
                  <span className={`text-xs font-medium shrink-0 ${
                    r.status === "safe" ? "text-green-600" : "text-red-600"
                  }`}>
                    {r.status === "safe" ? "安全" : "有违规"}
                  </span>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
