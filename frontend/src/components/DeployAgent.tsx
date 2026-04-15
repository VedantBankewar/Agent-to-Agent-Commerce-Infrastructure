import { Link } from 'react-router-dom';

export default function DeployAgent() {
  return (
    <div className="bg-background min-h-screen overflow-x-hidden flex flex-col items-center justify-center">
      {/* Floating Brand Logo */}
      <Link className="fixed top-8 left-8 z-50 text-2xl font-bold text-[#f9abff] font-headline tracking-tight hover:opacity-80 transition-opacity" to="/">
        AgentTrade
      </Link>
      
      {/* Main Content Canvas */}
      <main className="w-full flex-1 flex flex-col items-center justify-center px-6 relative py-20">
        {/* Ambient Background Glow */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-primary/5 rounded-full blur-[120px] pointer-events-none"></div>
        <div className="absolute top-1/3 left-1/4 w-[300px] h-[300px] bg-secondary/5 rounded-full blur-[100px] pointer-events-none"></div>
        
        <section className="w-full max-w-3xl z-10">
          {/* Header Group */}
          <div className="mb-12 text-center">
            <span className="text-[10px] font-bold tracking-[0.2em] text-secondary uppercase mb-3 block">New Deployment</span>
            <h1 className="text-4xl md:text-6xl font-headline font-extrabold text-on-surface tracking-tight leading-none mb-4">
              Deploy your <span className="text-primary italic">Mandate</span>
            </h1>
            <p className="text-on-surface-variant/70 text-lg max-w-xl mx-auto font-body">Define the objective, set the parameters, and let the Oracle execute across the multi-chain ecosystem.</p>
          </div>
          
          {/* Central Core Action */}
          <div className="agent-mandate-focus bg-surface-container-low rounded-xl p-2 transition-all duration-500 border border-outline-variant/10">
            <div className="relative flex flex-col gap-2 p-6 bg-surface-container-highest/30 rounded-lg">
              <label className="text-xs font-semibold text-primary/60 uppercase tracking-widest ml-1" htmlFor="mandate">Agent Mandate</label>
              <textarea className="w-full bg-transparent border-none text-2xl md:text-3xl font-body text-on-surface placeholder:text-on-surface-variant/20 resize-none focus:ring-none outline-none min-h-[160px] leading-relaxed" id="mandate" placeholder="e.g., 'Execute a high-frequency supply chain acquisition for 200 units of titanium alloy, optimizing for immediate delivery and minimum cost...'"></textarea>
              <div className="flex flex-col md:flex-row justify-between items-center mt-6 pt-6 border-t border-outline-variant/10 gap-4">
                <div className="flex items-center gap-6">
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-secondary text-sm">bolt</span>
                    <span className="text-xs font-label text-on-surface-variant">Priority: High</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-primary text-sm">account_balance</span>
                    <span className="text-xs font-label text-on-surface-variant">Limit: 2.5 ETH</span>
                  </div>
                </div>
                <button className="bg-primary text-on-primary px-10 py-4 rounded-md font-headline font-bold text-base hover:glow-soft active:scale-95 transition-all flex items-center gap-2 group">
                  Deploy Agent
                  <span className="material-symbols-outlined group-hover:translate-x-1 transition-transform">arrow_forward</span>
                </button>
              </div>
            </div>
          </div>
          
          {/* Linear Pipeline Indicator */}
          <div className="mt-16 w-full max-w-2xl mx-auto">
            <div className="flex justify-between items-end mb-4">
              <h3 className="text-xs font-bold uppercase tracking-widest text-on-surface-variant/60">Readiness Pipeline</h3>
              <span className="text-[10px] font-label text-secondary px-2 py-0.5 rounded-full bg-secondary/10 border border-secondary/20">Optimizing...</span>
            </div>
            <div className="relative h-[2px] w-full bg-surface-container-highest overflow-hidden">
              <div className="pipeline-gradient absolute h-full w-[65%] top-0 left-0 shadow-[0_0_10px_rgba(249,171,255,0.4)]"></div>
            </div>
            <div className="grid grid-cols-4 mt-6 gap-2">
              <div className="flex flex-col gap-1">
                <span className="text-[10px] text-primary font-bold uppercase">Identity</span>
                <span className="text-xs text-on-surface-variant/80">Verified</span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-[10px] text-primary font-bold uppercase">Nodes</span>
                <span className="text-xs text-on-surface-variant/80">Allocated</span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-[10px] text-secondary font-bold uppercase">Logic</span>
                <span className="text-xs text-on-surface-variant/80">Compiling</span>
              </div>
              <div className="flex flex-col gap-1 opacity-30">
                <span className="text-[10px] text-on-surface-variant font-bold uppercase">Execution</span>
                <span className="text-xs text-on-surface-variant/80">Queued</span>
              </div>
            </div>
          </div>
        </section>
      </main>
      
      {/* Contextual "Agent Pulse" Decorative Element */}
      <div className="fixed bottom-12 right-12 hidden lg:flex items-center justify-center bg-[#1c1b1b]/40 backdrop-blur-md p-4 rounded-xl border border-outline-variant/10">
        <div className="relative">
          <div className="absolute inset-0 rounded-full bg-secondary w-2 h-2 m-auto"></div>
          <div className="w-10 h-10 rounded-full border border-primary/20 animate-[pulse_3s_infinite] opacity-30"></div>
          <div className="absolute inset-[-8px] rounded-full border border-primary/10 animate-[pulse_4s_infinite] opacity-10"></div>
        </div>
        <div className="ml-4">
          <div className="text-[10px] font-bold text-on-surface tracking-widest uppercase">Oracle Pulse</div>
          <div className="text-[10px] text-on-surface-variant/50">Steady • 24ms Latency</div>
        </div>
      </div>
    </div>
  );
}
