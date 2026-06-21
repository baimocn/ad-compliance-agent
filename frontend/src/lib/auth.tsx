"use client"

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react"
import { useRouter } from "next/navigation"

const TOKEN_KEY = "ad_agent_token"
const USER_KEY = "ad_agent_username"
const API_BASE = "http://localhost:8001"

interface User {
  userId: number
  username: string
}

interface AuthContextType {
  user: User | null
  token: string | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  register: (username: string, password: string) => Promise<void>
  logout: () => void
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    const savedToken = localStorage.getItem(TOKEN_KEY)
    const savedUser = localStorage.getItem(USER_KEY)
    if (savedToken && savedUser) {
      fetch(`${API_BASE}/api/me`, {
        headers: { Authorization: `Bearer ${savedToken}` },
      })
        .then((res) => {
          if (res.ok) return res.json()
          throw new Error("Token expired")
        })
        .then((data) => {
          setUser({ userId: data.user_id, username: data.username })
          setToken(savedToken)
        })
        .catch(() => {
          localStorage.removeItem(TOKEN_KEY)
          localStorage.removeItem(USER_KEY)
        })
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    })
    const data = await res.json()
    if (!res.ok || !data.success) {
      throw new Error(data.detail || data.error || "登录失败")
    }
    localStorage.setItem(TOKEN_KEY, data.token)
    localStorage.setItem(USER_KEY, data.username)
    setToken(data.token)
    setUser({ userId: data.user_id, username: data.username })
  }, [])

  const register = useCallback(async (username: string, password: string) => {
    const res = await fetch(`${API_BASE}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    })
    const data = await res.json()
    if (!res.ok || !data.success) {
      throw new Error(data.detail || data.error || "注册失败")
    }
    localStorage.setItem(TOKEN_KEY, data.token)
    localStorage.setItem(USER_KEY, data.username)
    setToken(data.token)
    setUser({ userId: data.user_id, username: data.username })
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setToken(null)
    setUser(null)
    router.push("/")
  }, [router])

  return (
    <AuthContext.Provider
      value={{
        user, token, loading,
        login, register, logout,
        isAuthenticated: !!token && !!user,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used within AuthProvider")
  return ctx
}
