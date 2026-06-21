"use client"

import { useState } from "react"
import Link from "next/link"
import { Loader2, Check, AlertTriangle, ArrowLeft, ShieldCheck } from "lucide-react"
import { forgotPassword, resetPassword } from "@/lib/api"

export default function ForgotPasswordPage() {
  const [step, setStep] = useState<"username" | "reset" | "done">("username")
  const [username, setUsername] = useState("")
  const [resetToken, setResetToken] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [error, setError] = useState("")
  const [submitting, setSubmitting] = useState(false)

  const handleRequestReset = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setSubmitting(true)
    try {
      const data = await forgotPassword(username)
      setResetToken(data.reset_token)
      setStep("reset")
    } catch (err: any) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setSubmitting(true)
    try {
      await resetPassword(username, resetToken, newPassword)
      setStep("done")
    } catch (err: any) {
      setError(err.message)
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
          <h1 className="text-2xl font-bold tracking-tight text-[#0a0a0a]">重置密码</h1>
          <p className="text-sm text-gray-400 mt-1">
            {step === "username" && "输入用户名获取重置令牌"}
            {step === "reset" && "输入新密码完成重置"}
            {step === "done" && "密码已重置"}
          </p>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-2xl bg-red-50 border border-red-100 px-4 py-3 text-sm text-red-600">
          <AlertTriangle className="size-4 shrink-0" />
          {error}
        </div>
      )}

      {step === "username" && (
        <form onSubmit={handleRequestReset} className="space-y-5">
          <div className="space-y-2">
            <label className="text-[13px] font-medium text-gray-500">用户名</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="请输入注册时的用户名"
              required
              className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066ff]/20 focus:border-[#0066ff]/30 transition-all"
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="w-full btn-primary inline-flex items-center justify-center gap-2 rounded-full bg-[#0a0a0a] px-4 py-3 text-sm font-semibold text-white shadow-sm hover:bg-[#262626] transition-all disabled:opacity-50"
          >
            {submitting ? <Loader2 className="size-4 animate-spin" /> : null}
            {submitting ? "处理中…" : "获取重置令牌"}
          </button>
          <p className="text-xs text-gray-400 text-center">
            重置令牌会直接显示在页面上（hackathon 阶段）
          </p>
        </form>
      )}

      {step === "reset" && (
        <form onSubmit={handleReset} className="space-y-5">
          <div className="rounded-2xl bg-blue-50 border border-blue-100 p-3 text-sm text-[#0066ff]">
            重置令牌：<code className="font-mono text-xs break-all">{resetToken}</code>
          </div>
          <div className="space-y-2">
            <label className="text-[13px] font-medium text-gray-500">新密码</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="至少8位，包含字母和数字"
              required
              className="w-full rounded-2xl border border-gray-200 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066ff]/20 focus:border-[#0066ff]/30 transition-all"
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="w-full btn-primary inline-flex items-center justify-center gap-2 rounded-full bg-[#0a0a0a] px-4 py-3 text-sm font-semibold text-white shadow-sm hover:bg-[#262626] transition-all disabled:opacity-50"
          >
            {submitting ? <Loader2 className="size-4 animate-spin" /> : null}
            {submitting ? "重置中…" : "重置密码"}
          </button>
        </form>
      )}

      {step === "done" && (
        <div className="text-center space-y-4">
          <div className="inline-flex size-12 items-center justify-center rounded-full bg-emerald-50">
            <Check className="size-6 text-emerald-500" />
          </div>
          <p className="text-sm text-gray-500">密码已重置，请使用新密码登录。</p>
          <Link
            href="/login"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-[#0066ff] hover:underline"
          >
            <ArrowLeft className="size-3" /> 返回登录
          </Link>
        </div>
      )}
    </div>
  )
}