export default function Capabilities() {
  return (
    <section className="min-h-screen flex items-center justify-center px-10 relative overflow-hidden py-32 pt-40" id="features">
      <div className="max-w-screen-2xl w-full relative z-10">
        <div className="text-center mb-20 space-y-4">
          <span className="text-primary font-label text-xs font-bold uppercase tracking-[0.3em] block">CAPABILITIES</span>
          <h2 className="text-5xl md:text-7xl font-headline font-extrabold text-on-background tracking-tight">Powered by Advanced AI</h2>
          <p className="text-lg text-on-surface-variant/60 font-body max-w-2xl mx-auto">Enterprise-grade autonomous agents built for the future of commerce</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="glass-panel rounded-[2rem] p-10 hover:border-primary/40 transition-all duration-500 group flex flex-col h-full">
            <div className="w-14 h-14 bg-primary/10 rounded-2xl flex items-center justify-center mb-8 border border-primary/20 group-hover:bg-primary/20 transition-colors">
              <span className="material-symbols-outlined text-primary text-3xl">bolt</span>
            </div>
            <h3 className="text-2xl font-headline font-bold text-on-background mb-6">Autonomous Procurement</h3>
            <p className="text-on-surface-variant/80 leading-relaxed font-body">AI agents independently discover and evaluate suppliers across global markets in real-time</p>
          </div>
          <div className="glass-panel rounded-[2rem] p-10 hover:border-primary/40 transition-all duration-500 group flex flex-col h-full">
            <div className="w-14 h-14 bg-primary/10 rounded-2xl flex items-center justify-center mb-8 border border-primary/20 group-hover:bg-primary/20 transition-colors">
              <span className="material-symbols-outlined text-primary text-3xl">shield</span>
            </div>
            <h3 className="text-2xl font-headline font-bold text-on-background mb-6">Smart Negotiations</h3>
            <p className="text-on-surface-variant/80 leading-relaxed font-body">Advanced ML algorithms negotiate optimal terms and pricing without human intervention</p>
          </div>
          <div className="glass-panel rounded-[2rem] p-10 hover:border-primary/40 transition-all duration-500 group flex flex-col h-full">
            <div className="w-14 h-14 bg-primary/10 rounded-2xl flex items-center justify-center mb-8 border border-primary/20 group-hover:bg-primary/20 transition-colors">
              <span className="material-symbols-outlined text-primary text-3xl">account_tree</span>
            </div>
            <h3 className="text-2xl font-headline font-bold text-on-background mb-6">Blockchain Settlement</h3>
            <p className="text-on-surface-variant/80 leading-relaxed font-body">Instant, transparent payment settlement on Algorand with cryptographic verification</p>
          </div>
          <div className="glass-panel rounded-[2rem] p-10 hover:border-primary/40 transition-all duration-500 group flex flex-col h-full">
            <div className="w-14 h-14 bg-primary/10 rounded-2xl flex items-center justify-center mb-8 border border-primary/20 group-hover:bg-primary/20 transition-colors">
              <span className="material-symbols-outlined text-primary text-3xl">trending_up</span>
            </div>
            <h3 className="text-2xl font-headline font-bold text-on-background mb-6">Adaptive Learning</h3>
            <p className="text-on-surface-variant/80 leading-relaxed font-body">Agents continuously learn and improve procurement strategies from market dynamics</p>
          </div>
        </div>
      </div>
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-primary/5 blur-[150px] rounded-full pointer-events-none"></div>
    </section>
  );
}
