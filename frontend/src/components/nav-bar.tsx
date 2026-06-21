"use client";

import { useState, useRef, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  ShieldCheck, FileSearch, BarChart3, History,
  LogIn, UserPlus, LogOut, ChevronDown, User,
} from "lucide-react";
import { useAuth } from "@/lib/auth";

export function NavBar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const isHome = pathname === "/";
  const isAuthPage = pathname.startsWith("/login") || pathname.startsWith("/register") || pathname.startsWith("/forgot-password");

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node))
        setMenuOpen(false);
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // On non-home pages OR when scrolled, show glass background
  const showGlass = !isHome || scrolled;

  const navItems = [
    { href: "/review", label: "审查", icon: FileSearch },
    { href: "/stats", label: "数据看板", icon: BarChart3 },
    ...(isAuthenticated
      ? [{ href: "/history", label: "历史", icon: History }]
      : []),
  ];

  return (
    <header
      className={`fixed top-0 z-50 w-full transition-all duration-300 ${
        showGlass
          ? "glass-nav shadow-[0_1px_0_rgba(0,0,0,0.04)]"
          : "bg-transparent"
      }`}
    >
      <div className="mx-auto flex h-16 max-w-[1290px] items-center justify-between px-5 sm:px-6">
        {/* Logo */}
        <button
          onClick={() => router.push("/")}
          className="flex items-center gap-2.5 hover:opacity-70 transition-opacity cursor-pointer"
        >
          <div className="flex items-center justify-center size-8 rounded-[10px] bg-[#0a0a0a]">
            <ShieldCheck className="size-4 text-white" />
          </div>
          <span className="text-[15px] font-bold tracking-tight text-[#0a0a0a] hidden sm:inline">
            合规 AI
          </span>
        </button>

        {/* Nav */}
        <nav className="flex items-center gap-1">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;
            return (
              <button
                key={item.href}
                onClick={() => router.push(item.href)}
                className={`inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-[13px] font-medium transition-all duration-200 cursor-pointer
                  ${
                    isActive
                      ? "bg-[#0a0a0a] text-white shadow-sm"
                      : "text-gray-500 hover:text-[#0a0a0a] hover:bg-gray-100"
                  }`}
              >
                <Icon className="size-3.5" />
                <span className="hidden sm:inline">{item.label}</span>
              </button>
            );
          })}

          <div className="w-px h-4 bg-gray-200 mx-2" />

          {/* Auth section */}
          {isAuthenticated ? (
            <div className="relative" ref={menuRef}>
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                className="inline-flex items-center gap-1.5 rounded-full pl-1.5 pr-3 py-1.5 text-[13px] font-medium text-gray-500 hover:bg-gray-100 hover:text-[#0a0a0a] transition-all duration-200 cursor-pointer"
              >
                <div className="flex items-center justify-center size-7 rounded-full bg-[#0a0a0a]">
                  <User className="size-3.5 text-white" />
                </div>
                <span className="hidden sm:inline max-w-20 truncate">
                  {user?.username}
                </span>
                <ChevronDown className="size-3" />
              </button>
              {menuOpen && (
                <div className="absolute right-0 top-full mt-2 w-44 rounded-2xl border border-gray-200 bg-white p-1.5 shadow-[0_16px_64px_-12px_rgba(0,0,0,0.12)]">
                  <button
                    onClick={() => {
                      router.push("/settings");
                      setMenuOpen(false);
                    }}
                    className="w-full flex items-center gap-2.5 rounded-xl px-3 py-2 text-[13px] text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer"
                  >
                    <User className="size-3.5 text-gray-400" /> 个人设置
                  </button>
                  <div className="my-1 h-px bg-gray-100" />
                  <button
                    onClick={() => {
                      logout();
                      setMenuOpen(false);
                    }}
                    className="w-full flex items-center gap-2.5 rounded-xl px-3 py-2 text-[13px] text-gray-400 hover:bg-gray-50 hover:text-red-500 transition-colors cursor-pointer"
                  >
                    <LogOut className="size-3.5" /> 退出登录
                  </button>
                </div>
              )}
            </div>
          ) : (
            !isAuthPage && (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => router.push("/login")}
                  className="inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-[13px] font-medium text-gray-500 hover:text-[#0a0a0a] hover:bg-gray-100 transition-all duration-200 cursor-pointer"
                >
                  <LogIn className="size-3.5" />
                  <span className="hidden sm:inline">登录</span>
                </button>
                <button
                  onClick={() => router.push("/register")}
                  className="inline-flex items-center gap-1.5 rounded-full bg-[#0a0a0a] px-4 py-2 text-[13px] font-medium text-white hover:bg-[#262626] transition-all duration-200 cursor-pointer"
                >
                  <UserPlus className="size-3.5" />
                  <span className="hidden sm:inline">注册</span>
                </button>
              </div>
            )
          )}
        </nav>
      </div>
    </header>
  );
}