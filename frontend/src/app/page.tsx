"use client";

import { PixelHero } from "@/components/ui/pixel-perfect-hero";

export default function Home() {
  return (
    <PixelHero
      word1="广告"
      word2="合规 AI"
      description="输入文案，10秒审查违规风险。一次罚款20万，我们帮你提前规避。"
      primaryCta="开始审查"
      primaryCtaMobile="审查"
      secondaryCta="查看文档"
      secondaryCtaMobile="文档"
      onPrimaryClick={() => window.location.href = "/review"}
      githubUrl="https://github.com"
    />
  );
}
