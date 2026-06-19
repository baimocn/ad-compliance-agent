import React from "react";
import { PixelHero } from "@/components/ui/pixel-perfect-hero";

export default function Demo() {
  return (
    <div className="w-full min-h-screen bg-background">
      <PixelHero
        word1="Silent"
        word2="Precision."
        description="Interfaces with refined motion. Every calculated detail delivers an elevated digital experience."
        primaryCta="Explore Design"
        primaryCtaMobile="Explore"
        secondaryCta="View GitHub"
        secondaryCtaMobile="GitHub"
        onPrimaryClick={() => console.log("Primary click action triggered.")}
        onSecondaryClick={() => console.log("Secondary click action triggered.")}
        githubUrl="https://github.com"
      />
    </div>
  );
}
