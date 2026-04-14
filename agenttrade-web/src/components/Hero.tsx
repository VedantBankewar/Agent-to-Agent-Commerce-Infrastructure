import { Button } from "@/components/ui/button";
import { Play, Sparkles } from "lucide-react";

export function Hero() {
  return (
    <section className="relative min-h-[921px] flex items-center overflow-hidden px-6 pt-20">
      {/* Background Video */}
      <video
        autoPlay
        loop
        muted
        playsInline
        className="absolute inset-0 w-full h-full object-cover"
        style={{ zIndex: 0 }}
      >
        <source src="/vdo.mp4" type="video/mp4" />
      </video>

      {/* Dark Overlay */}
      <div className="absolute inset-0 bg-surface/60" style={{ zIndex: 1 }} />

      {/* Background Glow */}
      <div className="absolute inset-0 hero-glow" style={{ zIndex: 2 }} />

      {/* Bottom Fade */}
      <div
        className="absolute bottom-0 left-0 right-0 h-64"
        style={{
          zIndex: 3,
          background:
            "linear-gradient(to top, #16121a 0%, #16121acc 30%, #16121a66 60%, transparent 100%)",
        }}
      />

      <div
        className="relative max-w-3xl mx-auto text-center py-32"
        style={{ zIndex: 4 }}
      >
        {/* Badge */}
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-surface-container-high border border-outline-variant/20 mb-8">
          <Sparkles className="w-4 h-4 text-tertiary" />
          <span className="text-xs font-bold tracking-widest uppercase text-tertiary">
            New Era of Intelligence
          </span>
        </div>

        {/* Headline */}
        <h1 className="text-6xl md:text-7xl lg:text-8xl font-extrabold font-headline leading-[1.05] tracking-tighter text-on-surface mb-8">
          The Future of{" "}
          <span className="bg-clip-text text-transparent bg-gradient-to-b from-primary to-primary-container">
            AI Trading
          </span>
        </h1>

        {/* Subheadline */}
        <p className="text-lg md:text-xl text-on-surface-variant max-w-xl mx-auto font-body leading-relaxed mb-10">
          Unleash autonomous agents that navigate the markets for you. Precision
          execution meets generative intelligence.
        </p>

        {/* CTA Buttons */}
        <div className="flex flex-col sm:flex-row justify-center gap-4">
          <Button size="lg" className="rounded-xl">
            Get Early Access
          </Button>
          <Button
            variant="secondary"
            size="lg"
            className="rounded-xl border-outline-variant"
          >
            <Play className="w-5 h-5" />
            Watch Demo
          </Button>
        </div>

        {/* Floating Data Card */}
        <div className="mt-16 inline-flex glass-panel p-6 rounded-2xl shadow-2xl animate-pulse">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-2 h-2 rounded-full bg-tertiary amber-accent" />
            <span className="text-[10px] uppercase font-bold tracking-widest text-tertiary">
              Active Agent
            </span>
          </div>
          <div className="text-2xl font-headline font-bold text-on-surface">
            +$4,290.12
          </div>
          <div className="text-xs text-primary font-semibold">
            Alpha-Bot 7 Executed Profit
          </div>
        </div>
      </div>
    </section>
  );
}
