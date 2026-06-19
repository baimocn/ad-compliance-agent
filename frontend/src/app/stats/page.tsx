"use client"

import { useEffect, useState } from "react"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { getStats } from "@/lib/api"
import type { StatsResponse, Severity } from "@/types/review"
import {
  BarChart3,
  ShieldAlert,
  FileSearch,
  Loader2,
  AlertCircle,
  TrendingUp,
} from "lucide-react"

// ---------------------------------------------------------------------------
// Risk label helper
// ---------------------------------------------------------------------------

const SEVERITY_LABEL: Record<Severity, string> = {
  high: "高风险",
  medium: "中风险",
  low: "低风险",
  pass: "通过",
}

const SEVERITY_COLOR: Record<Severity, string> = {
  high: "bg-red-500",
  medium: "bg-amber-500",
  low: "bg-green-500",
  pass: "bg-gray-400",
}

const SEVERITY_BADGE_CLASS: Record<Severity, string> = {
  high: "bg-red-100 text-red-800 border-red-300",
  medium: "bg-amber-100 text-amber-800 border-amber-300",
  low: "bg-green-100 text-green-800 border-green-300",
  pass: "bg-gray-100 text-gray-700 border-gray-300",
}

// ---------------------------------------------------------------------------
// Average risk score: high=3, medium=2, low=1, pass=0
// ---------------------------------------------------------------------------

function calcAvgRisk(data: StatsResponse): string {
  const weights: Record<Severity, number> = {
    high: 3,
    medium: 2,
    low: 1,
    pass: 0,
  }
  let totalWeight = 0
  let totalCount = 0
  for (const item of data.violationBySeverity) {
    totalWeight += (weights[item.severity] ?? 0) * item.count
    totalCount += item.count
  }
  if (totalCount === 0) return "0.0"
  return (totalWeight / totalCount).toFixed(1)
}

// ---------------------------------------------------------------------------
// Stat Card
// ---------------------------------------------------------------------------

function StatCard({
  icon,
  label,
  value,
  sub,
}: {
  icon: React.ReactNode
  label: string
  value: string | number
  sub?: string
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4">
        <div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-muted">
          {icon}
        </div>
        <div className="min-w-0">
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="text-2xl font-bold tracking-tight">{value}</p>
          {sub && (
            <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Violation Bar Chart (pure div width %)
// ---------------------------------------------------------------------------

function CategoryBarChart({
  items,
}: {
  items: { category: string; count: number }[]
}) {
  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-4 text-center">
        暂无违规数据
      </p>
    )
  }

  const maxCount = Math.max(...items.map((i) => i.count))

  return (
    <div className="space-y-3">
      {items.map((item) => {
        const pct = maxCount > 0 ? (item.count / maxCount) * 100 : 0
        return (
          <div key={item.category} className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span className="truncate">{item.category}</span>
              <span className="font-medium tabular-nums text-muted-foreground">
                {item.count}
              </span>
            </div>
            <div className="h-2.5 w-full rounded-full bg-muted overflow-hidden">
              <div
                className="h-full rounded-full bg-primary transition-all duration-500"
                style={{ width: `${Math.max(pct, 2)}%` }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Recent Reviews Table
// ---------------------------------------------------------------------------

function RecentReviewsTable({
  reviews,
}: {
  reviews: StatsResponse["recentReviews"]
}) {
  if (reviews.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-4 text-center">
        暂无审查记录
      </p>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-muted-foreground">
            <th className="pb-2 pr-4 font-medium">审查 ID</th>
            <th className="pb-2 pr-4 font-medium">文案摘要</th>
            <th className="pb-2 pr-4 font-medium">风险等级</th>
            <th className="pb-2 pr-4 font-medium">违规数</th>
            <th className="pb-2 font-medium">状态</th>
          </tr>
        </thead>
        <tbody>
          {reviews.map((r) => (
            <tr key={r.reviewId} className="border-b last:border-0">
              <td className="py-2.5 pr-4 font-mono text-xs text-muted-foreground max-w-[100px] truncate">
                {r.reviewId}
              </td>
              <td className="py-2.5 pr-4 max-w-[200px] truncate">
                {r.text}
              </td>
              <td className="py-2.5 pr-4">
                <Badge
                  variant="outline"
                  className={SEVERITY_BADGE_CLASS[r.overallRisk]}
                >
                  {SEVERITY_LABEL[r.overallRisk]}
                </Badge>
              </td>
              <td className="py-2.5 pr-4 tabular-nums">{r.violationCount}</td>
              <td className="py-2.5">
                <span
                  className={
                    r.status === "safe"
                      ? "text-green-600"
                      : "text-red-600"
                  }
                >
                  {r.status === "safe" ? "安全" : "有违规"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

type PageState = "loading" | "error" | "ready"

export default function StatsPage() {
  const [state, setState] = useState<PageState>("loading")
  const [data, setData] = useState<StatsResponse | null>(null)

  useEffect(() => {
    let cancelled = false

    ;(async () => {
      try {
        const res = await getStats()
        if (!cancelled) {
          setData(res)
          setState("ready")
        }
      } catch {
        if (!cancelled) setState("error")
      }
    })()

    return () => {
      cancelled = true
    }
  }, [])

  // ---- Loading ----
  if (state === "loading") {
    return (
      <main className="min-h-screen bg-background">
        <div className="mx-auto max-w-5xl px-4 py-16 flex flex-col items-center justify-center gap-4">
          <Loader2 className="size-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">正在加载统计数据...</p>
        </div>
      </main>
    )
  }

  // ---- Error (backend not running) ----
  if (state === "error" || !data) {
    return (
      <main className="min-h-screen bg-background">
        <div className="mx-auto max-w-5xl px-4 py-16 flex flex-col items-center justify-center gap-4">
          <div className="rounded-full bg-muted p-4">
            <AlertCircle className="size-8 text-destructive" />
          </div>
          <h2 className="text-lg font-semibold">后端未启动</h2>
          <p className="text-sm text-muted-foreground text-center max-w-md">
            无法连接到后端 API 服务。请确保后端已启动并运行在{" "}
            <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
              {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}
            </code>
            ，然后刷新页面重试。
          </p>
        </div>
      </main>
    )
  }

  const avgRisk = calcAvgRisk(data)

  // ---- Ready ----
  return (
    <main className="min-h-screen bg-background">
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Header */}
        <header className="mb-8">
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <BarChart3 className="size-6 text-primary" />
            数据看板
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            广告合规审查系统的整体运行数据概览
          </p>
        </header>

        {/* KPI Cards */}
        <div className="grid gap-4 sm:grid-cols-3 mb-8">
          <StatCard
            icon={<FileSearch className="size-6 text-primary" />}
            label="总审查数"
            value={data.totalReviews}
          />
          <StatCard
            icon={<ShieldAlert className="size-6 text-destructive" />}
            label="总违规数"
            value={data.totalViolations}
          />
          <StatCard
            icon={<TrendingUp className="size-6 text-amber-600" />}
            label="平均风险分"
            value={avgRisk}
            sub="0-3 分，越高风险越大"
          />
        </div>

        {/* Violation by Category */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="size-5 text-primary" />
              违规类型分布
            </CardTitle>
            <CardDescription>
              按违规类别统计出现次数
            </CardDescription>
          </CardHeader>
          <CardContent>
            <CategoryBarChart items={data.violationByCategory} />
          </CardContent>
        </Card>

        {/* Recent Reviews */}
        <Card>
          <CardHeader>
            <CardTitle>近期审查记录</CardTitle>
            <CardDescription>
              最近提交的审查任务及其结果
            </CardDescription>
          </CardHeader>
          <CardContent>
            <RecentReviewsTable reviews={data.recentReviews} />
          </CardContent>
        </Card>
      </div>
    </main>
  )
}
