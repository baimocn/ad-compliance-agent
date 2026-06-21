"use client"

import { useState, FormEvent } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { ShieldCheck, Loader2, Eye, EyeOff } from "lucide-react"
import { useAuth } from "@/lib/auth"

export default function LoginPage() {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const { login } = useAuth()
  const router = useRouter()

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!username.trim() || !password) return
    setError("")
    setSubmitting(true)
    try {
      await login(username.trim(), password)
      router.push("/")
    } catch (err: any) {
      setError(err.message || "登录失败，请稍后重试")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-8">
      <div className="text-center space-y-3">
        <div className="flex items-center justify-center size-14 rounded-2xl bg-[#0a0a0a] mx-auto">
          <ShieldCheck className="size-7 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#0a0a0a]">欢迎回来</h1>
          <p className="text-sm text-gray-400 mt-1">登录后可使用审查历史等全部功能</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {error && (
          <div className="rounded-2xl bg-red-50 border border-red-100 px-4 py-3 text-sm text-red-600">
            {error}
          </div>
        )}

        <div className="space-y-2">
          <label className="text-[13px] font-medium text-gray-500">用户名</label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="请输入用户名"
            required
            className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066ff]/20 focus:border-[#0066ff]/30 transition-all"
          />
        </div>

        <div className="space-y-2">
          <label className="text-[13px] font-medium text-gray-500">密码</label>
          <div className="relative">
            <input
              type={showPw ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入密码"
              required
              className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-sm pr-10 focus:outline-none focus:ring-2 focus:ring-[#0066ff]/20 focus:border-[#0066ff]/30 transition-all"
            />
            <button
              type="button"
              onClick={() => setShowPw(!showPw)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-300 hover:text-gray-500 transition-colors"
            >
              {showPw ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full btn-primary inline-flex items-center justify-center gap-2 rounded-full bg-[#0a0a0a] px-4 py-3 text-sm font-semibold text-white shadow-sm hover:bg-[#262626] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? <Loader2 className="size-4 animate-spin" /> : null}
          {submitting ? "登录中…" : "登录"}
        </button>
      </form>

      <div className="flex items-center justify-between text-sm">
        <Link href="/register" className="font-medium text-[#0066ff] hover:underline">
          立即注册
        </Link>
        <Link href="/forgot-password" className="text-gray-400 hover:text-gray-600 transition-colors">
          忘记密码？
        </Link>
      </div>
    </div>
  )
}