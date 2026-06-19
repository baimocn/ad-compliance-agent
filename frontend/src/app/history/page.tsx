"use client"

import { useEffect, useState, useCallback } from "react"
import {
  Card, CardContent, CardHeader, CardTitle, CardDescription,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Clock, FileText, ChevronLeft, ChevronRight,
  AlertTriangle, ShieldCheck, Loader2, ArrowRight,
} from "lucide-react"
import { listReviews, type ReviewListItem } from "@/lib/api"
import Link from "next/link"

// ── Helpers ──────────────────────────────────────────────────

const RISK_CONFIG: Record<string, { label: string; className: string }> = {
  high:   { label: "高风险", className: "bg-red-100 text-red-800 border-red-300" },
  medium: { label: "中风险", className: "bg-amber-100 text-amber-800 border-amber-300" },
  low:    { label: "低风险", className: "bg-green-100 text-green-800 border-green-300" },
  pass:   { label: "通过",   className: "bg-gray-100 text-gray-700 border-gray-300" },
}

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  safe:            { label: "安全", className: "bg-emerald-100 text-emerald-700" },
  violation_found: { label: "违规", className: "bg-red-100 text-red-700" },
  error:           { label: "错误", className: "bg-gray-100 text-gray-500" },
}

const INDUSTRY_LABEL: Record<string, string> = {
  general: "通用",
  food: "食品",
  cosmetic: "化妆品",
  medicine: "医药",
  education: "教育",
  real_estate: "房地产",
  finance: "金融",
  ecommerce: "电商",
  manufacturing: "制造",
  healthcare: "医疗",
  technology: "科技",
  food_service: "餐饮",
  beauty: "美容",
  corporate: "企业",
}

// ── Page ─────────────────────────────────────────────────────

export default function HistoryPage() {
  const [reviews, setReviews] = useState<ReviewListItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pageSize = 20

  const loadReviews = useCallback(async (p: number) => {
    setLoading(true)
    setError(null)
    try {
      const result = await listReviews(pageSize, (p - 1) * pageSize)
      setReviews(result.reviews)
      setTotal(result.total)
    } catch (err: any) {
      setError(err.message || "加载失败")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadReviews(page)
  }, [page, loadReviews])

  const totalPages = Math.ceil(total / pageSize)

  return (
    <main className="min-h-screen bg-background">
      <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="mb-8">
          <h1 className="text-2xl font-bold tracking-tight">审查历史</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            查看所有历史审查记录，共 {total} 条
          </p>
        </header>

        {/* Error */}
        {error && (
          <Card className="border-red-200 bg-red-50/50 mb-6">
            <CardContent className="flex items-center gap-3 py-4">
              <AlertTriangle className="size-5 text-red-500 shrink-0" />
              <p className="text-sm text-red-700">{error}</p>
              <Button size="sm" variant="ghost" className="ml-auto" onClick={() => loadReviews(page)}>
                <Loader2 className="size-3" /> 重试
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Review list */}
        <div className="space-y-3">
          {loading && reviews.length === 0 && (
            <Card>
              <CardContent className="flex items-center justify-center py-12">
                <Loader2 className="size-6 animate-spin text-muted-foreground" />
              </CardContent>
            </Card>
          )}

          {!loading && reviews.length === 0 && !error && (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12 text-center">
                <FileText className="size-12 text-muted-foreground/40 mb-3" />
                <p className="text-sm text-muted-foreground">暂无审查记录</p>
                <Link href="/review">
                  <Button size="sm" className="mt-4">
                    去审查
                    <ArrowRight className="size-3" />
                  </Button>
                </Link>
              </CardContent>
            </Card>
          )}

          {reviews.map((review) => {
            const riskCfg = RISK_CONFIG[review.overallRisk] || RISK_CONFIG.pass
            const statusCfg = STATUS_CONFIG[review.status] || STATUS_CONFIG.error
            return (
              <Card key={review.reviewId} className="hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => {}}>
                <CardContent className="flex items-start gap-4 py-4">
                  <div className={`shrink-0 size-10 rounded-full flex items-center justify-center
                    ${review.overallRisk === "pass" || review.overallRisk === "low"
                      ? "bg-emerald-100" : "bg-red-100"}`}>
                    {review.overallRisk === "pass" || review.overallRisk === "low" ? (
                      <ShieldCheck className="size-5 text-emerald-600" />
                    ) : (
                      <AlertTriangle className="size-5 text-red-600" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant="outline" className={`text-xs ${riskCfg.className}`}>
                        {riskCfg.label}
                      </Badge>
                      <Badge variant="secondary" className="text-xs">
                        {statusCfg.label}
                      </Badge>
                      {review.violationCount > 0 && (
                        <span className="text-xs text-muted-foreground">
                          {review.violationCount} 处违规
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-foreground truncate">
                      {review.textPreview || "(空文本)"}
                    </p>
                    <div className="flex items-center gap-3 mt-1.5 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Clock className="size-3" />
                        {review.createdAt ? new Date(review.createdAt).toLocaleString("zh-CN") : "-"}
                      </span>
                      <span>{INDUSTRY_LABEL[review.industry] || review.industry}</span>
                      <span className="font-mono text-[10px] opacity-60">
                        {review.reviewId}
                      </span>
                    </div>
                  </div>
                  <ArrowRight className="size-4 text-muted-foreground/40 shrink-0 mt-1" />
                </CardContent>
              </Card>
            )
          })}
        </div>

        {/* Pagination */}
        {total > pageSize && (
          <div className="flex items-center justify-center gap-2 mt-8">
            <Button
              size="sm"
              variant="outline"
              disabled={page <= 1 || loading}
              onClick={() => setPage(p => Math.max(1, p - 1))}>
              <ChevronLeft className="size-4" />
              上一页
            </Button>
            <span className="text-sm text-muted-foreground px-4">
              第 {page} / {totalPages} 页，共 {total} 条
            </span>
            <Button
              size="sm"
              variant="outline"
              disabled={page >= totalPages || loading}
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}>
              下一页
              <ChevronRight className="size-4" />
            </Button>
          </div>
        )}
      </div>
    </main>
  )
}
