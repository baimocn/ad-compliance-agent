'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth'
import { Loader2, Check, Zap } from 'lucide-react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'
const TOKEN_KEY = 'ad_agent_token'

interface Plan {
  id: string
  name: string
  price: number
  max_reviews: number
  max_batch: number
  features: string
}

export default function PricingPage() {
  const { user, loading: authLoading } = useAuth()
  const router = useRouter()
  const [plans, setPlans] = useState<Plan[]>([])
  const [currentPlanId, setCurrentPlanId] = useState('free')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [upgrading, setUpgrading] = useState<string | null>(null)

  useEffect(() => {
    if (authLoading) return
    setLoading(true)
    setError('')
    Promise.all([
      fetch(`${API_BASE}/api/plans`).then(r => r.json()),
      user ? fetch(`${API_BASE}/api/my-plan`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem(TOKEN_KEY)}` }
      }).then(r => r.json()) : Promise.resolve({ plan: null })
    ]).then(([plansRes, planRes]) => {
      if (plansRes.success) setPlans(plansRes.plans)
      if (planRes?.plan) setCurrentPlanId(planRes.plan.id)
    }).catch(() => {
      setError('无法加载套餐信息，请确认后端服务已启动')
    }).finally(() => setLoading(false))
  }, [user, authLoading])

  const handleUpgrade = async (planId: string) => {
    if (!user) { router.push('/login'); return }
    if (planId === currentPlanId) return
    setUpgrading(planId)
    try {
      const res = await fetch(`${API_BASE}/api/simulate-payment`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem(TOKEN_KEY)}` },
        body: JSON.stringify({ plan_id: planId })
      })
      const data = await res.json()
      if (data.success) {
        setCurrentPlanId(planId)
        alert(`已成功${data.message}`)
      } else {
        alert(data.detail || '升级失败')
      }
    } catch {
      alert('网络错误')
    } finally {
      setUpgrading(null)
    }
  }

  return (
    <div className="min-h-screen bg-white pt-20">
      <main className="max-w-5xl mx-auto px-6 pt-24 pb-16">
        <div className="text-center mb-16">
          <span className="inline-block text-xs font-semibold text-[#0066ff] tracking-widest uppercase mb-3">
            Pricing
          </span>
          <h1 className="text-3xl sm:text-4xl font-bold text-[#0a0a0a] mb-4">
            套餐与定价
          </h1>
          <p className="text-gray-500 max-w-lg mx-auto">
            选择适合您业务规模的套餐，随时升级
          </p>
        </div>

        {loading ? (
          <div className="flex justify-center py-20">
            <Loader2 className="size-8 animate-spin text-gray-300" />
          </div>
        ) : error ? (
          <div className="max-w-md mx-auto text-center py-20">
            <div className="rounded-[28px] bg-red-50 border border-red-100 p-6">
              <p className="text-sm font-medium text-red-600">{error}</p>
              <button onClick={() => window.location.reload()} className="mt-4 text-sm text-[#0066ff] hover:underline">
                重试
              </button>
            </div>
          </div>
        ) : (
          <div className="grid md:grid-cols-3 gap-6">
            {plans.map(plan => {
              const isCurrent = plan.id === currentPlanId
              const isFree = plan.id === 'free'
              const isPro = plan.id === 'pro'
              return (
                <div
                  key={plan.id}
                  className={`rounded-[28px] p-8 border transition-all duration-400 flex flex-col ${
                    isCurrent
                      ? 'border-[#0066ff] bg-white shadow-[0_20px_60px_-15px_rgba(0,102,255,0.12)] scale-[1.02]'
                      : 'border-gray-200 bg-white hover:shadow-[0_20px_60px_-15px_rgba(0,0,0,0.06)] hover:border-gray-300'
                  }`}
                >
                  {isPro && (
                    <div className="inline-flex items-center gap-1.5 text-xs font-semibold text-white bg-gradient-to-r from-[#0066ff] to-blue-400 rounded-full px-3 py-1 self-start mb-4">
                      <Zap className="size-3" /> 推荐
                    </div>
                  )}
                  {isPro && <div className="h-7" />}

                  <h2 className="text-xl font-bold text-[#0a0a0a]">{plan.name}</h2>
                  <div className="mt-4 mb-6">
                    <span className="text-4xl font-extrabold text-[#0a0a0a] tracking-tight">¥{plan.price}</span>
                    <span className="text-gray-400 text-sm ml-1">{isFree ? '' : '/月'}</span>
                  </div>

                  <ul className="space-y-3 text-gray-600 text-sm flex-1">
                    <li className="flex items-center gap-2.5">
                      <div className="size-5 rounded-full bg-emerald-50 flex items-center justify-center shrink-0">
                        <Check className="size-3 text-emerald-500" />
                      </div>
                      每日上限 {plan.max_reviews === -1 ? '∞' : `${plan.max_reviews}次`}
                    </li>
                    <li className="flex items-center gap-2.5">
                      <div className="size-5 rounded-full bg-emerald-50 flex items-center justify-center shrink-0">
                        <Check className="size-3 text-emerald-500" />
                      </div>
                      批量上限 {plan.max_batch === -1 ? '∞' : `${plan.max_batch}次`}
                    </li>
                    <li className="flex items-center gap-2.5">
                      <div className="size-5 rounded-full bg-emerald-50 flex items-center justify-center shrink-0">
                        <Check className="size-3 text-emerald-500" />
                      </div>
                      {plan.features}
                    </li>
                  </ul>

                  <button
                    onClick={() => handleUpgrade(plan.id)}
                    disabled={isCurrent || upgrading === plan.id}
                    className={`mt-8 w-full py-3 rounded-full font-semibold text-sm transition-all ${
                      isCurrent
                        ? 'bg-gray-100 text-gray-400 cursor-default'
                        : upgrading === plan.id
                          ? 'bg-[#0066ff]/60 text-white cursor-wait'
                          : 'btn-primary bg-[#0a0a0a] text-white hover:bg-[#262626] active:scale-[0.98]'
                    }`}
                  >
                    {isCurrent ? '当前套餐' : upgrading === plan.id ? '处理中…' : isFree ? '免费使用' : '立即升级'}
                  </button>
                </div>
              )
            })}
          </div>
        )}

        <p className="text-center text-xs text-gray-400 mt-12">
          * hackathon 阶段为模拟支付，无需真实付款
        </p>
      </main>
    </div>
  )
}