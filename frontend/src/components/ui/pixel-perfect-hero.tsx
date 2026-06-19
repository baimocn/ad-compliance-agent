"use client";

import { ShieldCheck, FileSearch, Zap, ArrowRight, ExternalLink } from "lucide-react";

interface PixelHeroProps {
  word1: string;
  word2: string;
  description: string;
  primaryCta: string;
  primaryCtaMobile: string;
  secondaryCta: string;
  secondaryCtaMobile: string;
  onPrimaryClick?: () => void;
  onSecondaryClick?: () => void;
  githubUrl?: string;
}

export function PixelHero({
  word1,
  word2,
  description,
  primaryCta,
  primaryCtaMobile,
  secondaryCta,
  secondaryCtaMobile,
  onPrimaryClick,
  githubUrl,
}: PixelHeroProps) {
  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Grid pattern background */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.1) 1px, transparent 1px)",
          backgroundSize: "64px 64px",
        }}
      />

      {/* Gradient glow orbs */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl" />

      {/* Pixel grid accent dots */}
      <div className="absolute top-20 right-20 grid grid-cols-5 gap-2 opacity-20">
        {Array.from({ length: 25 }).map((_, i) => (
          <div
            key={i}
            className="w-2 h-2 rounded-full bg-emerald-400"
            style={{ opacity: Math.random() * 0.5 + 0.5 }}
          />
        ))}
      </div>
      <div className="absolute bottom-32 left-16 grid grid-cols-4 gap-3 opacity-15">
        {Array.from({ length: 16 }).map((_, i) => (
          <div
            key={i}
            className="w-1.5 h-1.5 rounded-full bg-blue-400"
            style={{ opacity: Math.random() * 0.6 + 0.4 }}
          />
        ))}
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-6 py-20 text-center">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-4 py-1.5 text-sm text-emerald-400 mb-8">
          <ShieldCheck className="w-4 h-4" />
          <span>AI 驱动的广告合规审查</span>
        </div>

        {/* Title */}
        <h1 className="text-5xl sm:text-6xl md:text-7xl lg:text-8xl font-bold tracking-tight mb-6">
          <span className="bg-gradient-to-r from-white via-white to-slate-400 bg-clip-text text-transparent">
            {word1}
          </span>
          <br />
          <span className="bg-gradient-to-r from-emerald-400 via-blue-400 to-violet-400 bg-clip-text text-transparent">
            {word2}
          </span>
        </h1>

        {/* Description */}
        <p className="max-w-2xl mx-auto text-lg sm:text-xl text-slate-400 leading-relaxed mb-10">
          {description}
        </p>

        {/* CTA Buttons */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
          <button
            onClick={onPrimaryClick}
            className="group relative inline-flex items-center justify-center gap-2 rounded-full bg-gradient-to-r from-emerald-500 to-blue-500 px-8 py-4 text-base font-semibold text-white shadow-lg shadow-emerald-500/25 transition-all hover:shadow-xl hover:shadow-emerald-500/30 hover:scale-105"
          >
            <FileSearch className="w-5 h-5" />
            <span className="hidden sm:inline">{primaryCta}</span>
            <span className="sm:hidden">{primaryCtaMobile}</span>
            <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
          </button>

          <a
            href={githubUrl ?? "#"}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-2 rounded-full border border-slate-700 bg-slate-800/50 px-8 py-4 text-base font-semibold text-slate-300 transition-all hover:bg-slate-800 hover:text-white hover:border-slate-600"
          >
            <ExternalLink className="w-5 h-5" />
            <span className="hidden sm:inline">{secondaryCta}</span>
            <span className="sm:hidden">{secondaryCtaMobile}</span>
          </a>
        </div>

        {/* Feature highlights */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 max-w-3xl mx-auto">
          <FeatureCard
            icon={<Zap className="w-5 h-5 text-amber-400" />}
            title="10 秒出结果"
            desc="毫秒级文案扫描"
          />
          <FeatureCard
            icon={<ShieldCheck className="w-5 h-5 text-emerald-400" />}
            title="覆盖全平台"
            desc="抖音 / 小红书 / 微信等"
          />
          <FeatureCard
            icon={<FileSearch className="w-5 h-5 text-blue-400" />}
            title="法规知识库"
            desc="持续更新广告法条文"
          />
        </div>
      </div>

      {/* Bottom gradient fade */}
      <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-slate-950 to-transparent" />
    </section>
  );
}

function FeatureCard({
  icon,
  title,
  desc,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
}) {
  return (
    <div className="group flex flex-col items-center gap-3 rounded-2xl border border-slate-800 bg-slate-900/50 p-6 transition-all hover:border-slate-700 hover:bg-slate-800/50">
      <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-slate-800 border border-slate-700 group-hover:border-slate-600 transition-colors">
        {icon}
      </div>
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      <p className="text-xs text-slate-500">{desc}</p>
    </div>
  );
}
