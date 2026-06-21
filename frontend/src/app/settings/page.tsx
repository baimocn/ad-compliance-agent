"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { ShieldCheck, Eye, EyeOff, Check, Save, Loader2, LogOut, User, Zap, Trash2, AlertTriangle } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth"
import { testConnection, deleteAccount } from "@/lib/api"

const DEFAULT_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
const DEFAULT_MODEL = "mimo-v2.5"

export default function SettingsPage() {
  const { user, isAuthenticated, loading: authLoading, logout } = useAuth()
  const router = useRouter()

  const [apiKey, setApiKey] = useState("")
  const [baseUrl, setBaseUrl] = useState(DEFAULT_BASE_URL)
  const [model, setModel] = useState(DEFAULT_MODEL)
  const [showKey, setShowKey] = useState(false)
  const [saved, setSaved] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string } | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    if (typeof window === "undefined") return
    setApiKey(localStorage.getItem("ad_agent_api_key") || "")
    setBaseUrl(localStorage.getItem("ad_agent_base_url") || DEFAULT_BASE_URL)
    setModel(localStorage.getItem("ad_agent_model") || DEFAULT_MODEL)
  }, [])

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login")
    }
  }, [authLoading, isAuthenticated, router])

  const handleSave = () => {
    localStorage.setItem("ad_agent_api_key", apiKey)
    localStorage.setItem("ad_agent_base_url", baseUrl)
    localStorage.setItem("ad_agent_model", model)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const handleTest = async () => {
    if (!apiKey) return
    setTesting(true)
    setTestResult(null)
    try {
      const data = await testConnection(apiKey, baseUrl, model)
      setTestResult({ ok: true, msg: data.message })
    } catch (err: any) {
      const msg = err.message || "连接测试失败"
      let hint = ""
      if (msg.includes("429") || msg.includes("quota") || msg.includes("limit")) {
        hint = "（API 频率限制，请等待 1-2 分钟后重试）"
      } else if (msg.includes("401") || msg.includes("Invalid") || msg.includes("invalid")) {
        hint = "（API Key 无效，请检查后重新输入）"
      } else if (msg.includes("400") || msg.includes("Not supported")) {
        hint = `（模型名称错误，当前填写：${model}，请改为 mimo-v2.5）`
      } else if (msg.includes("fetch") || msg.includes("network") || msg.includes("ECONNREFUSED")) {
        hint = "（后端服务未启动）"
      }
      setTestResult({ ok: false, msg: msg + hint })
    } finally {
      setTesting(false)
    }
  }

  const handleDeleteAccount = async () => {
    setDeleting(true)
    try {
      await deleteAccount()
      logout()
      router.push("/register")
    } catch (err: any) {
      alert(err.message)
    } finally {
      setDeleting(false)
    }
  }

  if (authLoading) {
    return (
      <div className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!isAuthenticated) return null

  const hasKey = !!apiKey

  return (
    <main className="min-h-[calc(100vh-3.5rem)] bg-background">
      <div className="mx-auto max-w-2xl px-4 pt-24 pb-8 sm:px-6 lg:px-8 space-y-6">
        <header>
          <h1 className="text-[22px] font-bold tracking-tight text-[#0a0a0a] flex items-center gap-2">
            <ShieldCheck className="size-6 text-[#0066ff]" />
            个人设置
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            管理你的 API 配置和账号信息
          </p>
        </header>

        {/* Account info */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <User className="size-4" />
              账号信息
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">用户名</span>
              <span className="text-sm font-medium">{user?.username}</span>
            </div>
            <Button variant="outline" size="sm" onClick={logout} className="text-destructive border-destructive/30 hover:bg-destructive/10">
              <LogOut className="size-3.5" />
              退出登录
            </Button>
          </CardContent>
        </Card>

        {/* API Config */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldCheck className="size-4" />
              API 配置
              <span className={`ml-auto size-2 rounded-full ${hasKey ? "bg-green-500" : "bg-amber-500"}`} />
            </CardTitle>
            <CardDescription>配置 LLM API 密钥和模型参数</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">API Key</label>
              <div className="relative">
                <input
                  type={showKey ? "text" : "password"}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="输入你的 API Key"
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm pr-9 focus:outline-none focus:ring-2 focus:ring-ring"
                />
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                >
                  {showKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium">Base URL</label>
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder={DEFAULT_BASE_URL}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <p className="text-xs text-muted-foreground">支持任何 OpenAI 兼容接口的 Base URL</p>
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium">模型名称</label>
              <input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder={DEFAULT_MODEL}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <p className="text-xs text-muted-foreground">
                推荐：<code className="bg-muted px-1 rounded">mimo-v2.5</code>（小米 MiMo 推理模型）
              </p>
            </div>

            <div className="flex gap-2">
              <Button onClick={handleSave} className="flex-1">
                {saved ? <><Check className="size-4" /> 已保存</> : <><Save className="size-4" /> 保存配置</>}
              </Button>
              <Button onClick={handleTest} variant="outline" disabled={!apiKey || testing} className="shrink-0">
                {testing ? <Loader2 className="size-4 animate-spin" /> : <Zap className="size-4" />}
                测试连接
              </Button>
            </div>

            {testResult && (
              <div className={`flex items-center gap-2 rounded-md p-3 text-sm border ${
                testResult.ok ? "bg-green-50 text-green-700 border-green-200" : "bg-red-50 text-red-700 border-red-200"
              }`}>
                {testResult.ok ? <Check className="size-4 shrink-0" /> : <AlertTriangle className="size-4 shrink-0" />}
                {testResult.msg}
              </div>
            )}

            <p className="text-xs text-muted-foreground">API Key 仅存储在浏览器本地，不会上传到服务器。</p>
          </CardContent>
        </Card>

        {/* Danger Zone */}
        <Card className="border-red-200">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base text-red-700">
              <Trash2 className="size-4" />
              危险操作
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!confirmDelete ? (
              <Button variant="outline" size="sm" onClick={() => setConfirmDelete(true)} className="text-red-600 border-red-300 hover:bg-red-50">
                注销账户
              </Button>
            ) : (
              <div className="space-y-3">
                <p className="text-sm text-red-700">确定要注销账户？所有数据将被永久删除，不可恢复。</p>
                <div className="flex gap-2">
                  <Button size="sm" variant="destructive" onClick={handleDeleteAccount} disabled={deleting}>
                    {deleting ? <Loader2 className="size-3 animate-spin" /> : null}
                    确认注销
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setConfirmDelete(false)}>取消</Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  )
}