export default function Solution() {
  return (
    <section className="min-h-screen flex items-center justify-center px-10 relative overflow-hidden py-32 pt-40" id="solution">
      <div className="max-w-screen-2xl w-full flex flex-col md:flex-row items-center gap-20">
        <div className="flex-1 flex justify-center items-center">
          <div className="concentric-rings scale-75 md:scale-100">
            <div className="ring ring-1"></div>
            <div className="ring ring-2"></div>
            <div className="ring ring-3"></div>
            <div className="ring ring-inner blur-xl opacity-40"></div>
            <div className="absolute inset-0 bg-primary/5 rounded-full blur-[100px]"></div>
          </div>
        </div>
        <div className="flex-1 space-y-8">
          <div className="space-y-4">
            <span className="text-primary font-label text-xs font-bold uppercase tracking-[0.3em] block">THE AGENTTRADE SOLUTION</span>
            <h2 className="text-5xl md:text-7xl font-headline font-extrabold text-on-background tracking-tight">Fully Autonomous Commerce</h2>
          </div>
          <p className="text-lg text-on-surface-variant/80 font-body leading-relaxed max-w-xl">
            AgentTrade deploys intelligent AI agents that operate 24/7, autonomously managing the entire procurement lifecycle. From supplier discovery to contract negotiation and instant blockchain settlement — your commerce runs on autopilot.
          </p>
          <div className="pt-10 grid grid-cols-3 gap-8">
            <div>
              <div className="text-4xl md:text-5xl font-headline font-extrabold text-primary mb-2">10x</div>
              <div className="text-[10px] md:text-xs font-label font-bold text-on-surface-variant tracking-[0.2em] uppercase">FASTER PROCUREMENT</div>
            </div>
            <div>
              <div className="text-4xl md:text-5xl font-headline font-extrabold text-primary mb-2">95%</div>
              <div className="text-[10px] md:text-xs font-label font-bold text-on-surface-variant tracking-[0.2em] uppercase">COST REDUCTION</div>
            </div>
            <div>
              <div className="text-4xl md:text-5xl font-headline font-extrabold text-primary mb-2">&lt;1s</div>
              <div className="text-[10px] md:text-xs font-label font-bold text-on-surface-variant tracking-[0.2em] uppercase">SETTLEMENT TIME</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
