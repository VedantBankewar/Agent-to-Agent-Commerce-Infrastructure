import { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export default function DeployAgent() {
  const [goal, setGoal] = useState("");
  const [logs, setLogs] = useState<string[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [isFinished, setIsFinished] = useState(false);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const [dealDetails, setDealDetails] = useState<{
    txid?: string;
    deal_hash?: string;
    app_id?: string;
    supplier?: string;
    total?: string;
    delivery?: string;
  }>({});
  const [quotes, setQuotes] = useState<{
    id: string;
    supplier: string;
    score: number;
    price: string;
    delivery: string;
    warranty: string;
    isWinner: boolean;
  }[]>([]);

  const presetGoals = [
    "Buy 50 ergonomic chairs, budget 10, by June 15",
    "Buy 100 pens, budget 5, by May 1",
    "Buy 10 desks, budget 20, by August 2026"
  ];

  const scrollToBottom = () => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [logs]);

  const runPipeline = async () => {
    if (!goal || isRunning) return;
    setIsRunning(true);
    setLogs([]);
    setQuotes([]);
    setIsFinished(false);
    setDealDetails({});

    try {
      const response = await fetch(`${API_BASE}/api/run_pipeline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goal })
      });

      if (!response.body) return;
      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim();
            if (data === '[DONE]') {
              setIsFinished(true);
              setIsRunning(false);
              return;
            }
            if (data) {
              const cleanData = data
                .replace(/[\u001b\x1b]\[[0-9;]*[a-zA-Z]/g, '')
                .replace(/\[[0-9]{1,2}m/g, '');
              
              setLogs(prev => [...prev, cleanData]);

              // Background parsing for Live Profile
              if (cleanData.includes('deal_hash:')) {
                setDealDetails(prev => ({ ...prev, deal_hash: cleanData.split('deal_hash:')[1].trim() }));
              }
              if (cleanData.includes('txid:') && !cleanData.includes('Funded app')) {
                setDealDetails(prev => ({ ...prev, txid: cleanData.split('txid:')[1].trim() }));
              }
              if (cleanData.includes('app_id:') && !cleanData.includes('Created')) {
                setDealDetails(prev => ({ ...prev, app_id: cleanData.split('app_id:')[1].trim() }));
              }
              if (cleanData.includes('winner=')) {
                const parts = cleanData.split('winner=')[1];
                setDealDetails(prev => ({ ...prev, supplier: parts.split('  ')[0].trim() }));
              }
              if (cleanData.includes('total=')) {
                // e.g. total=$1.06  delivery=7d  warranty=2.0yr
                const parts = cleanData.split('total=')[1].split('  ');
                const total = parts[0];
                const delivery = parts.find(p => p.includes('delivery='))?.split('=')[1] || '';
                setDealDetails(prev => ({ ...prev, total, delivery }));
              }

              // Quote Parsing: Pattern for "👑 ChairHub: score=94.5 | $92.00/unit | 5d | 2.0yr"
              const quoteMatch = cleanData.match(/^\s*(👑)?\s*([^:]+):\s*score=([\d.]+)\s*\|\s*\$([\d.]+)\/unit\s*\|\s*(\d+)d\s*\|\s*([\d.]+)yr/);
              if (quoteMatch) {
                const [, isWinner, supplier, score, price, delivery, warranty] = quoteMatch;
                setQuotes(prev => {
                  if (prev.some(q => q.supplier === supplier.trim())) return prev;
                  return [...prev, {
                    id: Math.random().toString(36).substr(2, 9),
                    supplier: supplier.trim(),
                    score: parseFloat(score),
                    price: `$${price}`,
                    delivery: `${delivery}d`,
                    warranty: `${warranty}yr`,
                    isWinner: !!isWinner
                  }];
                });
              }
            }
          }
        }
      }
    } catch (e) {
      console.error("Stream failed:", e);
      setIsRunning(false);
    }
  };

  const releaseFunds = async () => {
    try {
      setIsFinished(false);
      setLogs(prev => [...prev, "\n=> TRIGGERING RELEASE_FUNDS.PY...\n"]);
      const response = await fetch(`${API_BASE}/api/release_funds`, { method: 'POST' });
      if (!response.body) return;
      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim();
            if (data === '[DONE]') {
              setIsFinished(true);
              return;
            }
            if (data) {
              const cleanData = data
                .replace(/[\u001b\x1b]\[[0-9;]*[a-zA-Z]/g, '')
                .replace(/\[[0-9]{1,2}m/g, '');
              setLogs(prev => [...prev, cleanData]);
              
              if (cleanData.includes('txid:')) {
                 setDealDetails(prev => ({ ...prev, txid: cleanData.split('txid:')[1].trim() }));
              }
            }
          }
        }
      }
    } catch (e) {
      console.error("Release stream failed:", e);
    }
  };

  const [logsHeight, setLogsHeight] = useState<'collapsed' | 'expanded'>('collapsed');

  const getPipelineStage = () => {
    if (!isRunning && !isFinished) return 0;
    const recent = logs.join(" ");
    
    // Stage 4: Execution / On-chain
    if (isFinished || recent.includes("Locking escrow") || recent.includes("TRIGGERING RELEASE")) return 4;
    // Stage 3: Logic / Algorithmic Selection
    if (recent.includes("Quotes scored") || recent.includes("Winner:")) return 3;
    // Stage 2: Nodes / Agent Negotiation
    if (recent.includes("RFQ broadcast") || recent.includes("generate_supplier_quotes")) return 2;
    // Stage 1: Identity / Market Discovery
    if (recent.includes("search") || recent.includes("Deploying")) return 1;
    
    return 1;
  };

  const pipelineStage = getPipelineStage();

  const pipelineSteps = [
    { label: "IDENTITY", sub: pipelineStage > 1 ? "Verified" : pipelineStage === 1 ? "Discovering" : "Waiting", active: pipelineStage >= 1 },
    { label: "NODES", sub: pipelineStage > 2 ? "Allocated" : pipelineStage === 2 ? "Negotiating" : "Queued", active: pipelineStage >= 2 },
    { label: "LOGIC", sub: pipelineStage > 3 ? "Computed" : pipelineStage === 3 ? "Scoring" : "Queued", active: pipelineStage >= 3 },
    { label: "EXECUTION", sub: isFinished ? "Settled" : pipelineStage === 4 ? "Compiling" : "Queued", active: pipelineStage >= 4 },
  ];

  const currentStep = () => {
    if (!isRunning && !isFinished) return "Waiting to start...";
    const recent = logs.slice(-10).join(" ");
    if (recent.includes("Searching") || recent.includes("search")) return "Discovering Suppliers";
    if (recent.includes("RFQ broadcast")) return "Negotiating Details";
    if (recent.includes("Quotes scored")) return "Evaluating Options";
    if (recent.includes("Locking escrow")) return "Anchoring Smart Contract";
    if (recent.includes("TRIGGERING RELEASE")) return "Verifying Delivery Proof";
    if (isFinished && dealDetails.txid) return "Funds Successfully Released";
    if (isFinished) return "Escrow Locked";
    return "Processing...";
  };

  return (
    <div className="bg-background min-h-screen text-on-surface font-body overflow-x-hidden selection:bg-primary-container selection:text-primary flex flex-col relative">
      {/* Floating Brand Logo */}
      <Link className="absolute top-8 left-10 z-[100] text-2xl font-bold text-primary font-headline tracking-tight hover:opacity-80 transition-opacity" to="/">
        AgentTrade
      </Link>

      {/* Main Content Canvas */}
      <main className="w-full flex-1 flex flex-col px-6 relative py-20 items-center">
        
        {/* Ambient Background Glow */}
        <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-primary/5 rounded-full blur-[120px] pointer-events-none z-0"></div>
        <div className="fixed top-1/3 left-1/4 w-[300px] h-[300px] bg-secondary/5 rounded-full blur-[100px] pointer-events-none z-0"></div>

        <section className="w-full max-w-screen-2xl z-10 flex flex-col gap-8">
          
          {/* Header Group */}
          <div className="mb-12 text-center mt-8">
            <span className="text-[10px] font-bold tracking-[0.2em] text-secondary uppercase mb-3 block">New Deployment</span>
            <h1 className="text-4xl md:text-6xl font-headline font-extrabold text-on-surface tracking-tight leading-none mb-4">
              Procurement <span className="text-primary italic">Agent</span>
            </h1>
            <p className="text-on-surface-variant/70 text-lg max-w-xl mx-auto font-body">
              Define the objective, set the parameters, and let the Oracle execute across the multi-chain ecosystem.
            </p>
          </div>

        {/* Dashboard Grid */}
        <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_1fr] gap-6">
          
          {/* Left Column */}
          <div className="flex flex-col gap-6">
            
            {/* Goal Card */}
            <div className="bg-surface-container-low border border-outline-variant/10 rounded-xl p-8 transition-all duration-500 shadow-xl">
              <div className="flex items-center gap-3 mb-8">
                <span className="material-symbols-outlined text-primary text-2xl">rocket_launch</span>
                <h2 className="text-xl font-bold text-on-surface font-headline tracking-wide">Procurement Goal</h2>
              </div>
              
              <div className="flex flex-col md:flex-row gap-4 mb-4">
                <div className="flex-1 bg-[#111111] border border-white/10 rounded-xl focus-within:border-primary/50 transition-colors">
                  <input 
                    type="text" 
                    value={goal}
                    onChange={(e) => setGoal(e.target.value)}
                    placeholder="Buy 50 ergonomic chairs, budget 300000, by June 15"
                    className="w-full bg-transparent border-none text-white placeholder:text-on-surface-variant/40 px-4 py-4 font-body outline-none text-sm md:text-base font-mono"
                    disabled={isRunning}
                  />
                </div>
                <button 
                  onClick={runPipeline}
                  disabled={isRunning || !goal.trim()}
                  className={`px-8 py-4 rounded-xl font-bold flex items-center justify-center gap-2 transition-all ${
                    isRunning || !goal.trim() 
                      ? 'bg-outline-variant text-white/50 cursor-not-allowed' 
                      : 'bg-gradient-to-r from-primary-container to-primary text-white hover:opacity-90 shadow-[0_0_20px_rgba(249,171,255,0.3)] active:scale-95'
                  }`}
                >
                  <span className="material-symbols-outlined text-sm">{isRunning ? 'hourglass_empty' : 'rocket_launch'}</span>
                  <span>{isRunning ? 'Running...' : 'Run Pipeline'}</span>
                </button>
              </div>

              <div className="flex flex-wrap gap-2">
                {presetGoals.map((preset, idx) => (
                  <button 
                    key={idx}
                    onClick={() => setGoal(preset)}
                    className="bg-surface-container-highest/20 border border-outline-variant/10 px-4 py-2 rounded-full text-xs text-on-surface-variant/80 hover:bg-surface-container-highest/40 transition-colors text-left"
                    disabled={isRunning}
                  >
                    {preset}
                  </button>
                ))}
              </div>
            </div>

            {/* Readiness Pipeline Card */}
            <div className="bg-surface-container-low border border-outline-variant/10 rounded-2xl p-6 shadow-xl flex flex-col items-center justify-center">
              <div className="w-full flex justify-between items-center mb-6">
                <h3 className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/60">Readiness Pipeline</h3>
                <span className="text-[10px] font-label text-secondary px-2 py-0.5 rounded-full bg-secondary/10 border border-secondary/20">
                  {isRunning ? 'Optimizing...' : isFinished ? 'Completed' : 'Idle'}
                </span>
              </div>

              {/* Graphical Bar */}
              <div className="w-full h-[2px] bg-surface-container-highest relative mt-4 mb-8 overflow-hidden">
                <div 
                  className="absolute top-0 left-0 h-full bg-pipeline-gradient transition-all duration-1000 ease-out shadow-[0_0_10px_rgba(249,171,255,0.4)]"
                  style={{ width: `${pipelineStage === 0 ? 0 : (pipelineStage / 4) * 100}%` }}
                >
                </div>
              </div>

              {/* Labels */}
              <div className="w-full grid grid-cols-4 gap-4">
                {pipelineSteps.map((step, idx) => (
                  <div key={idx} className={`flex flex-col gap-1 ${step.active ? 'opacity-100' : 'opacity-30'}`}>
                    <span className={`text-[10px] font-bold uppercase ${
                      step.active && step.sub !== 'Queued' ? 'text-primary' : 'text-on-surface-variant'
                    }`}>
                      {step.label}
                    </span>
                    <span className="text-xs text-on-surface-variant/80">{step.sub}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Comparison Grid (Logic Phase) */}
            {(quotes.length > 0) && (
              <div className="bg-surface-container-low border border-outline-variant/10 rounded-2xl p-6 shadow-xl flex flex-col transition-all animate-in fade-in zoom-in duration-700">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex flex-col">
                    <span className="text-[10px] uppercase font-bold text-secondary tracking-widest mb-1">Comparative Analysis</span>
                    <h2 className="font-headline font-bold text-white tracking-wide">Multi-Agent Bidding</h2>
                  </div>
                  <div className="flex items-center gap-1.5 px-3 py-1 bg-white/5 rounded-full border border-white/10">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase">{quotes.length} {quotes.length === 1 ? 'Quote' : 'Quotes'} Received</span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {quotes.sort((a,b) => b.score - a.score).map((quote) => (
                    <div 
                      key={quote.id} 
                      className={`relative flex flex-col p-5 rounded-2xl border transition-all duration-500 ${
                        quote.isWinner 
                        ? 'bg-gradient-to-br from-primary/10 to-transparent border-primary/40 shadow-[0_0_20px_rgba(249,171,255,0.1)] scale-105 z-10 shimmer-bg' 
                        : 'bg-[#111111] border-white/5 opacity-70 grayscale-[0.3]'
                      }`}
                    >
                      {quote.isWinner && (
                        <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-primary text-on-primary text-[10px] font-bold px-3 py-1 rounded-full shadow-lg flex items-center gap-1 uppercase tracking-tight">
                          <span className="material-symbols-outlined text-[12px]">award</span>
                          Winner Selected
                        </div>
                      )}
                      
                      <div className="flex flex-col mb-4">
                        <span className={`text-xs font-bold uppercase tracking-widest mb-1 ${quote.isWinner ? 'text-primary' : 'text-on-surface-variant'}`}>{quote.supplier}</span>
                        <div className="flex items-baseline gap-1">
                          <span className="text-3xl font-bold font-headline text-white">{quote.score}</span>
                          <span className="text-[10px] text-on-surface-variant uppercase font-bold tracking-tight">/100</span>
                        </div>
                      </div>

                      <div className="space-y-3 pt-4 border-t border-white/5">
                        <div className="flex justify-between items-center text-xs">
                          <span className="text-on-surface-variant">Price</span>
                          <span className="text-white font-mono font-bold">{quote.price}</span>
                        </div>
                        <div className="flex justify-between items-center text-xs">
                          <span className="text-on-surface-variant">Speed</span>
                          <span className="text-white font-bold">{quote.delivery}</span>
                        </div>
                        <div className="flex justify-between items-center text-xs">
                          <span className="text-on-surface-variant">Warranty</span>
                          <span className="text-white font-bold">{quote.warranty}</span>
                        </div>
                      </div>

                      {quote.isWinner && (
                        <div className="mt-4 pt-3 flex justify-center">
                           <div className="w-1.5 h-1.5 rounded-full bg-primary animate-ping"></div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* System Feed (Collapsible) */}
            <div className={`bg-surface-container-low border border-white/5 rounded-2xl flex flex-col shadow-xl overflow-hidden transition-all duration-300 ${logsHeight === 'expanded' ? 'h-[300px]' : 'h-[60px]'}`}>
              <button 
                onClick={() => setLogsHeight(prev => prev === 'expanded' ? 'collapsed' : 'expanded')}
                className="w-full flex items-center justify-between p-4 hover:bg-white/5 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-[16px] text-white/50">terminal</span>
                  <span className="text-xs font-bold text-white tracking-widest uppercase">System Feed</span>
                </div>
                <span className="material-symbols-outlined text-white/50 text-[18px]">
                  {logsHeight === 'expanded' ? 'expand_less' : 'expand_more'}
                </span>
              </button>
              
              <div className="flex-1 bg-[#0a080c] p-4 overflow-y-auto font-mono text-[11px] md:text-xs text-on-surface-variant whitespace-pre-wrap leading-relaxed scrollbar-hide border-t border-white/5">
                {logs.length === 0 ? (
                  <div className="h-full flex items-center justify-center text-on-surface-variant/40">
                    Awaiting initialization...
                  </div>
                ) : (
                  <div className="flex flex-col gap-1">
                    {logs.map((log, i) => (
                      <span key={i} className={`
                        ${log.includes('=>') ? 'text-primary font-bold mt-2' : ''}
                        ${log.includes('Error') || log.includes('Failed') ? 'text-error' : ''}
                        ${log.includes('SUCCESS') || log.includes('COMPLETED') ? 'text-secondary font-bold' : ''}
                        ${log.includes('Goal:') || log.includes('Winner:') ? 'text-white font-bold' : ''}
                      `}>
                        {log}
                      </span>
                    ))}
                    <div ref={logsEndRef} />
                  </div>
                )}
              </div>
            </div>

          </div>

          {/* Right Column: Live Transactional Profile Card */}
          <div className="bg-transparent border border-white/5 rounded-3xl overflow-hidden shadow-2xl flex flex-col relative h-full min-h-[500px]">
            {/* Header/Tracking state */}
            <div className="bg-surface-container-low p-6 border-b border-white/5 flex items-center justify-between z-10 relative">
               <div className="flex flex-col">
                  <span className="text-[10px] uppercase tracking-[0.2em] font-bold text-on-surface-variant mb-1">State Profile</span>
                  <h3 className="text-xl font-bold font-headline text-white">{currentStep()}</h3>
               </div>
               <div className={`w-12 h-12 rounded-full border flex items-center justify-center transition-all ${
                 isRunning ? 'bg-primary/20 border-primary/50 text-primary animate-pulse' : 
                 isFinished && dealDetails.txid ? 'bg-secondary/20 border-secondary/50 text-secondary' : 
                 'bg-white/5 border-white/10 text-white/30'
               }`}>
                 <span className="material-symbols-outlined">{isRunning ? 'sync' : isFinished && dealDetails.txid ? 'task_alt' : 'bolt'}</span>
               </div>
            </div>

            {/* Ambient Background Behind Content */}
            <div className="absolute inset-x-0 bottom-0 top-24 overflow-hidden pointer-events-none z-0">
               <div className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full blur-[120px] transition-all duration-1000 ${
                 isRunning ? 'bg-primary/10' : isFinished ? 'bg-secondary/10' : 'bg-transparent'
               }`}></div>
            </div>

            {/* Profile Content */}
            <div className="flex-1 p-8 relative z-10 flex flex-col justify-center">
              {!dealDetails.supplier && !isRunning && !isFinished ? (
                 <div className="flex flex-col items-center justify-center text-center text-on-surface-variant/50 h-full">
                    <span className="material-symbols-outlined text-4xl mb-4">account_balance_wallet</span>
                    <p>Awaiting procurement request to generate on-chain deal variables...</p>
                 </div>
              ) : (
                <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 flex flex-col gap-6">
                   
                   {/* Deal High-level Summary */}
                   <div className="bg-[#111111] border border-white/5 rounded-2xl p-6">
                      <h4 className="text-white text-sm font-bold uppercase tracking-wider mb-6 flex items-center gap-2">
                        <span className="material-symbols-outlined text-primary text-sm">handshake</span> Active Deal
                      </h4>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="flex flex-col">
                          <span className="text-on-surface-variant text-xs mb-1">Supplier</span>
                          <span className="text-white font-bold text-lg">{dealDetails.supplier || 'Negotiating...'}</span>
                        </div>
                        <div className="flex flex-col">
                          <span className="text-on-surface-variant text-xs mb-1">Total Cost</span>
                          <span className="text-secondary font-bold text-lg">{dealDetails.total || 'Computing...'}</span>
                        </div>
                        <div className="flex flex-col mt-2">
                          <span className="text-on-surface-variant text-xs mb-1">Contract App ID</span>
                          <span className="text-primary font-mono text-sm">{dealDetails.app_id || 'Staging...'}</span>
                        </div>
                        <div className="flex flex-col mt-2">
                          <span className="text-on-surface-variant text-xs mb-1">Lead Time</span>
                          <span className="text-white font-mono text-sm">{dealDetails.delivery || 'TBD'}</span>
                        </div>
                      </div>
                   </div>

                   {/* Blockchain Hashes (Glassmorphism Receipt) */}
                   <div className="bg-gradient-to-br from-white/5 to-transparent border border-white/10 rounded-2xl p-6 backdrop-blur-md">
                      <h4 className="text-white text-sm font-bold uppercase tracking-wider mb-4 border-b border-white/5 pb-2">
                        Cryptographic Verification
                      </h4>
                      
                      <div className="flex flex-col gap-4 mt-4">
                        <div className="flex flex-col break-all">
                          <span className="text-on-surface-variant text-[10px] uppercase mb-1 flex items-center gap-1">
                            <span className="material-symbols-outlined text-[12px]">fingerprint</span> Algorand Hash
                          </span>
                          <span className="text-white/80 font-mono text-xs">{dealDetails.deal_hash || 'Building cryptographic proof...'}</span>
                        </div>
                        
                        <div className="flex flex-col break-all mt-2">
                          <span className="text-on-surface-variant text-[10px] uppercase mb-1 flex items-center gap-1">
                            <span className="material-symbols-outlined text-[12px]">receipt_long</span> Transaction ID
                          </span>
                          {dealDetails.txid ? (
                            <a 
                              href={`https://lora.algokit.io/testnet/transaction/${dealDetails.txid}`} 
                              target="_blank" 
                              rel="noreferrer"
                              className="text-primary hover:text-primary-container hover:underline font-mono text-xs flex items-center gap-1 transition-all"
                            >
                              {dealDetails.txid} <span className="material-symbols-outlined text-[10px]">open_in_new</span>
                            </a>
                          ) : (
                            <span className="text-white/80 font-mono text-xs">Waiting for blockchain settlement...</span>
                          )}
                        </div>
                      </div>
                   </div>

                   {/* Action Required: Fake the Delivery */}
                   {isFinished && (
                      <div className="mt-2 text-center animate-pulse">
                         <span className="text-xs text-secondary mb-4 block">Simulation required: Trigger physical delivery to execute <b>Payment Release</b> via contract validation.</span>
                         <button 
                          onClick={releaseFunds}
                           className="bg-[#241a00] border border-secondary/30 text-secondary hover:bg-secondary/20 px-8 py-3 rounded-full font-bold transition-all flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(255,215,153,0.1)] active:scale-95 w-full uppercase tracking-widest text-xs"
                         >
                           <span className="material-symbols-outlined text-sm">local_shipping</span>
                          Confirm Item Received
                         </button>
                      </div>
                   )}
                </div>
              )}
            </div>
          </div>

        </div>
        </section>

        {/* Contextual "Agent Pulse" Decorative Element */}
        <div className="fixed bottom-12 right-12 hidden lg:flex items-center justify-center bg-surface-container-low/40 backdrop-blur-md p-4 rounded-xl border border-outline-variant/10 z-50">
          <div className="relative">
            <div className="absolute inset-0 rounded-full bg-secondary w-2 h-2 m-auto"></div>
            <div className="w-10 h-10 rounded-full border border-primary/20 animate-pulse opacity-30"></div>
            <div className="absolute inset-[-8px] rounded-full border border-primary/10 animate-pulse opacity-10"></div>
          </div>
          <div className="ml-4">
            <div className="text-[10px] font-bold text-on-surface tracking-widest uppercase">Oracle Pulse</div>
            <div className="text-[10px] text-on-surface-variant/50">Steady • {isRunning ? '12ms' : '24ms'} Latency</div>
          </div>
        </div>
      </main>
    </div>
  );
}
