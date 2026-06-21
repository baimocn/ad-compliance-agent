"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { BarChart3, Loader2, AlertCircle, Zap, ChevronRight } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth"
import { getUsage } from "@/lib/api"

export default function UsagePage() {
  const { isAuthenticated, loading: authLoading } = useAuth()
  const router = useRouter()
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    if (authLoading) return
    if (!isAuthenticated) { router.push("/login"); return }
    ;(async () => {
      try {
        const res = await getUsage()
        if (res.success) setData(res)
        else setError("加载失败")
      } catch { setError("无法连接后端") }
      finally { setLoading(false) }
    })()
  }, [authLoading, isAuthenticated, router])

  if (authLoading || loading) {
    return (
      <div className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    )
  }
  if (!isAuthenticated) return null

  const plan = data?.plan ?? {}
  const today = data?.today ?? {}
  const month = data?.thisMonth ?? {}
  const limits = data?.limits ?? {}
  const isUnlimited = limits.maxReviews === -1

  const todayPct = isUnlimited ? 0 : limits.maxReviews > 0 ? Math.round((today.reviews / limits.maxReviews) * 100) : 0
  const monthPct = isUnlimited ? 0 : limits.maxReviews > 0 ? Math.round((month.reviews / limits.maxReviews) * 100) : 0

  return (
    <main className="min-h-[calc(100vh-3.5rem)] bg-background">
      <div className="mx-auto max-w-3xl px-4 pt-24 pb-8 sm:px-6 lg:px-8 space-y-6">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <BarChart3 className="size-6 text-primary" />
              我的用量
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">查看您的套餐详情和使用情况</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => router.push("/pricing")}>
            <Zap className="size-3.5" /> 升级套餐 <ChevronRight className="size-3" />
          </Button>
        </header>

        {error && (
          <Card className="border-red-200 bg-red-50/50">
            <CardContent className="flex items-center gap-3 py-4">
              <AlertCircle className="size-5 text-red-500 shrink-0" />
              <p className="text-sm text-red-700">{error}</p>
            </CardContent>
          </Card>
        )}

        {/* Current plan */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              当前套餐
              <Badge className="ml-auto text-xs">
                {plan.name || "免费版"}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              <div>
                <p className="text-xs text-muted-foreground">每日审查上限</p>
                <p className="text-lg font-bold">{isUnlimited ? "不限" : `${limits.maxReviews} 次`}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">每日批量上限</p>
                <p className="text-lg font-bold">{limits.maxBatch === -1 ? "不限" : `${limits.maxBatch} 次`}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">套餐价格</p>
                <p className="text-lg font-bold">¥{plan.price || 0}{plan.price > 0 ? "/月" : ""}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Today */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">今日用量</CardTitle>
            <CardDescription>今日已用 / 上限</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span>审查次数</span>
                <span className="font-medium tabular-nums">{today.reviews} / {isUnlimited ? "∞" : limits.maxReviews}</span>
              </div>
              {!isUnlimited && (
                <div className="h-2.5 w-full rounded-full bg-muted overflow-hidden">
                  <div className={`h-full rounded-full transition-all duration-500 ${
                    todayPct >= 80 ? "bg-red-500" : todayPct >= 50 ? "bg-amber-500" : "bg-primary"
                  }`} style={{ width: `${Math.min(todayPct, 100)}%` }} />
                </div>
              )}
            </div>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="rounded-lg bg-muted/50 p-3">
                <p className="text-muted-foreground text-xs">批量审查</p>
                <p className="font-semibold tabular-nums mt-0.5">{today.batches} 次</p>
              </div>
              <div className="rounded-lg bg-muted/50 p-3">
                <p className="text-muted-foreground text-xs">Token 用量</p>
                <p className="font-semibold tabular-nums mt-0.5">{today.tokens?.toLocaleString() || 0}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* This Month */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">本月累计</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-3 gap-4 text-sm">
            <div className="rounded-lg bg-muted/50 p-3">
              <p className="text-muted-foreground text-xs">审查</p>
              <p className="font-semibold tabular-nums mt-0.5">{month.reviews} 次</p>
            </div>
            <div className="rounded-lg bg-muted/50 p-3">
              <p className="text-muted-foreground text-xs">批量</p>
              <p className="font-semibold tabular-nums mt-0.5">{month.batches} 次</p>
            </div>
            <div className="rounded-lg bg-muted/50 p-3">
              <p className="text-muted-foreground text-xs">Token</p>
              <p className="font-semibold tabular-nums mt-0.5">{month.tokens?.toLocaleString() || 0}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </main>
  )
}
