import { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import ProcurementForm, { type ProcurementFormData } from './ProcurementForm';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export default function DeployAgent() {
  const [logs, setLogs] = useState<string[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [isFinished, setIsFinished] = useState(false);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const [formData, setFormData] = useState<ProcurementFormData | null>(null);
  const [dealDetails, setDealDetails] = useState<{
    txid?: string;
    deal_hash?: string;
    app_id?: string;
    supplier?: string;
    total?: string;
    delivery?: string;
    amount_usd?: string;
    amount_algo?: string;
    usd_rate?: string;
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
  const [negotiations, setNegotiations] = useState<{
    supplier: string;
    round: number;
    decision: string;
    message: string;
  }[]>([]);

  const [errorAnalysis, setErrorAnalysis] = useState<{
    type: string;
    details: string;
    solution: string;
  } | null>(null);

  const scrollToBottom = () => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [logs, negotiations]);

  const runPipeline = async (data: ProcurementFormData) => {
    if (isRunning) return;
    setFormData(data);
    setIsRunning(true);
    setLogs([]);
    setQuotes([]);
    setNegotiations([]);
    setIsFinished(false);
    setDealDetails({});
    setErrorAnalysis(null);

    try {
      const response = await fetch(`${API_BASE}/api/run_pipeline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
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
            const rawData = line.slice(6).trim();
            if (rawData === '[DONE]') {
              setIsFinished(true);
              setIsRunning(false);
              return;
            }
            if (rawData) {
              const cleanData = rawData
                .replace(/[\u001b\x1b]\[[0-9;]*[a-zA-Z]/g, '')
                .replace(/\[[0-9]{1,2}m/g, '');

              setLogs(prev => [...prev, cleanData]);

              // Parse deal details from output
              if (cleanData.includes('deal_hash:')) {
                setDealDetails(prev => ({ ...prev, deal_hash: cleanData.split('deal_hash:')[1]?.trim() }));
              }
              if (cleanData.includes('Deal ID:')) {
                setDealDetails(prev => ({ ...prev, deal_hash: cleanData.split('Deal ID:')[1]?.trim() }));
              }
              if (cleanData.includes('TX ID:') && !cleanData.includes('Funded')) {
                setDealDetails(prev => ({ ...prev, txid: cleanData.split('TX ID:')[1]?.trim() }));
              }
              if (cleanData.includes('txid:') && !cleanData.includes('Funded app')) {
                setDealDetails(prev => ({ ...prev, txid: cleanData.split('txid:')[1]?.trim() }));
              }
              if (cleanData.includes('app_id:') && !cleanData.includes('Created')) {
                setDealDetails(prev => ({ ...prev, app_id: cleanData.split('app_id:')[1]?.trim() }));
              }
              if (cleanData.includes('App ID:') && !cleanData.includes('Created')) {
                const appId = cleanData.match(/App ID:\s*(\d+)/)?.[1];
                if (appId) setDealDetails(prev => ({ ...prev, app_id: appId }));
              }

              // Parse USD amounts
              if (cleanData.includes('Amount:') && cleanData.includes('USD')) {
                const usdMatch = cleanData.match(/\$([\d,]+\.?\d*)\s*USD/);
                const algoMatch = cleanData.match(/([\d,]+\.?\d*)\s*ALGO/);
                if (usdMatch) setDealDetails(prev => ({ ...prev, amount_usd: `$${usdMatch[1]}`, total: `$${usdMatch[1]}` }));
                if (algoMatch) setDealDetails(prev => ({ ...prev, amount_algo: `${algoMatch[1]} ALGO` }));
              }
              if (cleanData.includes('Rate:') && cleanData.includes('ALGO')) {
                setDealDetails(prev => ({ ...prev, usd_rate: cleanData.split('Rate:')[1]?.trim() }));
              }

              // Parse supplier winner
              if (cleanData.includes('OFFER ACCEPTED')) {
                const supplierMatch = cleanData.match(/OFFER ACCEPTED.*?(\S+)$/);
                if (supplierMatch) setDealDetails(prev => ({ ...prev, supplier: supplierMatch[1] }));
              }
              if (cleanData.includes('winner=')) {
                const parts = cleanData.split('winner=')[1];
                setDealDetails(prev => ({ ...prev, supplier: parts?.split('  ')[0]?.trim() }));
              }

              // Parse quotes from output
              const quoteMatch = cleanData.match(/\[QUOTE\]\s*([^:]+):\s*\$([\d.]+)\/unit\s*\|\s*(\d+)d\s*\|\s*([\d.]+)yr.*?Score:\s*([\d.]+)/);
              if (quoteMatch) {
                const [, supplier, price, delivery, warranty, score] = quoteMatch;
                setQuotes(prev => {
                  if (prev.some(q => q.supplier === supplier.trim())) return prev;
                  return [...prev, {
                    id: Math.random().toString(36).substr(2, 9),
                    supplier: supplier.trim(),
                    score: parseFloat(score),
                    price: `$${price}`,
                    delivery: `${delivery}d`,
                    warranty: `${warranty}yr`,
                    isWinner: false,
                  }];
                });
              }

              // Legacy quote format
              const legacyQuoteMatch = cleanData.match(/^\s*(crown)?\s*([^:]+):\s*score=([\d.]+)\s*\|\s*\$([\d.]+)\/unit\s*\|\s*(\d+)d\s*\|\s*([\d.]+)yr/);
              if (legacyQuoteMatch) {
                const [, isWinner, supplier, score, price, delivery, warranty] = legacyQuoteMatch;
                setQuotes(prev => {
                  if (prev.some(q => q.supplier === supplier.trim())) return prev;
                  return [...prev, {
                    id: Math.random().toString(36).substr(2, 9),
                    supplier: supplier.trim(),
                    score: parseFloat(score),
                    price: `$${price}`,
                    delivery: `${delivery}d`,
                    warranty: `${warranty}yr`,
                    isWinner: !!isWinner,
                  }];
                });
              }

              // Parse negotiation events
              const counterMatch = cleanData.match(/\[(?:COUNTER ->|<- (ACCEPT|COUNTER|REJECT))\]/);
              if (counterMatch) {
                const decision = counterMatch[1] || 'SENT';
                const supplierPart = cleanData.match(/(?:To|From)\s+(\S+)/)?.[1] || '';
                const roundPart = cleanData.match(/Round\s+(\d+)/)?.[1] || '0';
                setNegotiations(prev => [...prev, {
                  supplier: supplierPart.substring(0, 20),
                  round: parseInt(roundPart),
                  decision,
                  message: cleanData.replace(/\[.*?\]/, '').trim().substring(0, 120),
                }]);
              }

              // Mark winner in quotes
              if (cleanData.includes('OFFER ACCEPTED') || cleanData.includes('Winner')) {
                setQuotes(prev => prev.map((q, i) => ({
                  ...q,
                  isWinner: i === 0 || cleanData.includes(q.supplier),
                })));
              }

              // Error detection
              const rawDataLower = cleanData.toLowerCase();
              let hasFatalError = false;

              if (rawDataLower.includes('overspend') || rawDataLower.includes('below min')) {
                const addressMatch = cleanData.match(/([A-Z2-7]{58})/);
                let addressInfo = addressMatch ? ` (${addressMatch[1]})` : '';
                setErrorAnalysis({
                  type: 'Liquidity Error',
                  details: 'Insufficient ALGO balance detected.',
                  solution: `Fund the wallet${addressInfo} from the Algorand Testnet Dispenser.`
                });
                hasFatalError = true;
              } else if (rawDataLower.includes('no llm api key') || rawDataLower.includes('api_key not set')) {
                setErrorAnalysis({
                  type: 'Configuration Error',
                  details: 'Missing LLM API key for autonomous agent.',
                  solution: 'Add ANTHROPIC_API_KEY or OPENAI_API_KEY to the root .env file and restart.'
                });
                hasFatalError = true;
              } else if (rawDataLower.includes('no suppliers found')) {
                setErrorAnalysis({
                  type: 'Market Discovery Error',
                  details: 'No suppliers match the requested category.',
                  solution: 'Ensure supplier data is seeded in the database.'
                });
                hasFatalError = true;
              } else if (rawDataLower.includes('no deploy_config.json')) {
                setErrorAnalysis({
                  type: 'Deployment Error',
                  details: 'Missing smart contract deployment configuration.',
                  solution: 'Run contracts/deploy.py first to deploy the escrow contract.'
                });
                hasFatalError = true;
              }

              if (hasFatalError) {
                setIsRunning(false);
                try { await reader.cancel(); } catch (e) {}
                return;
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
      setLogs(prev => [...prev, "\n=> TRIGGERING DELIVERY PROOF & PAYMENT RELEASE...\n"]);
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

              if (cleanData.includes('txid:') || cleanData.includes('TX ID:')) {
                const txid = cleanData.match(/(?:txid|TX ID):\s*(\S+)/)?.[1];
                if (txid) setDealDetails(prev => ({ ...prev, txid }));
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
    if (isFinished || recent.includes("ESCROW LOCKED") || recent.includes("TRIGGERING")) return 4;
    if (recent.includes("OFFER ACCEPTED") || recent.includes("COUNTER") || recent.includes("counter")) return 3;
    if (recent.includes("QUOTE") || recent.includes("quote") || recent.includes("RFQ")) return 2;
    if (recent.includes("DISCOVER") || recent.includes("search") || recent.includes("Deploying")) return 1;
    return 1;
  };

  const pipelineStage = getPipelineStage();

  const pipelineSteps = [
    { label: "DISCOVERY", sub: pipelineStage > 1 ? "Complete" : pipelineStage === 1 ? "Searching" : "Waiting", active: pipelineStage >= 1 },
    { label: "QUOTING", sub: pipelineStage > 2 ? "Received" : pipelineStage === 2 ? "Collecting" : "Queued", active: pipelineStage >= 2 },
    { label: "NEGOTIATION", sub: pipelineStage > 3 ? "Agreed" : pipelineStage === 3 ? "Negotiating" : "Queued", active: pipelineStage >= 3 },
    { label: "ESCROW", sub: isFinished ? "Settled" : pipelineStage === 4 ? "Locking" : "Queued", active: pipelineStage >= 4 },
  ];

  const currentStep = () => {
    if (!isRunning && !isFinished) return "Waiting to start...";
    const recent = logs.slice(-10).join(" ");
    if (recent.includes("DISCOVER") || recent.includes("search")) return "Discovering Suppliers";
    if (recent.includes("QUOTE") || recent.includes("RFQ")) return "Collecting Quotes";
    if (recent.includes("COUNTER") || recent.includes("NEGOTIAT")) return "Deep Negotiation";
    if (recent.includes("OFFER ACCEPTED")) return "Deal Agreed";
    if (recent.includes("ESCROW LOCKED")) return "Escrow Locked on Algorand";
    if (recent.includes("TRIGGERING")) return "Verifying Delivery Proof";
    if (isFinished && dealDetails.txid) return "Funds Successfully Released";
    if (isFinished) return "Procurement Complete";
    return "Agent Reasoning...";
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

          {/* Header */}
          <div className="mb-12 text-center mt-8">
            <span className="text-[10px] font-bold tracking-[0.2em] text-secondary uppercase mb-3 block">New Procurement</span>
            <h1 className="text-4xl md:text-6xl font-headline font-extrabold text-on-surface tracking-tight leading-none mb-4">
              Autonomous <span className="text-primary italic">Agent</span>
            </h1>
            <p className="text-on-surface-variant/70 text-lg max-w-xl mx-auto font-body">
              Define your procurement requirements. The autonomous agent will discover suppliers, negotiate deeply, and lock escrow on Algorand.
            </p>
          </div>

          {/* Dashboard Grid */}
          <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_1fr] gap-6">

            {/* Left Column */}
            <div className="flex flex-col gap-6">

              {/* Procurement Form Card */}
              <div className="bg-surface-container-low border border-outline-variant/10 rounded-xl p-8 transition-all duration-500 shadow-xl">
                <div className="flex items-center gap-3 mb-8">
                  <span className="material-symbols-outlined text-primary text-2xl">rocket_launch</span>
                  <h2 className="text-xl font-bold text-on-surface font-headline tracking-wide">Procurement Request</h2>
                  {formData && (
                    <span className={`ml-auto text-[10px] font-bold uppercase px-3 py-1 rounded-full ${
                      formData.priority === 'cost' ? 'bg-green-500/10 text-green-400 border border-green-500/20' :
                      formData.priority === 'speed' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' :
                      formData.priority === 'quality' ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20' :
                      'bg-white/5 text-white/60 border border-white/10'
                    }`}>
                      {formData.priority} priority
                    </span>
                  )}
                </div>
                <ProcurementForm onSubmit={runPipeline} disabled={isRunning} />
              </div>

              {/* Readiness Pipeline Card */}
              <div className="bg-surface-container-low border border-outline-variant/10 rounded-2xl p-6 shadow-xl flex flex-col items-center justify-center">
                <div className="w-full flex justify-between items-center mb-6">
                  <h3 className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/60">Agent Pipeline</h3>
                  <span className="text-[10px] font-label text-secondary px-2 py-0.5 rounded-full bg-secondary/10 border border-secondary/20">
                    {isRunning ? 'Active' : isFinished ? 'Completed' : 'Idle'}
                  </span>
                </div>

                <div className="w-full h-[2px] bg-surface-container-highest relative mt-4 mb-8 overflow-hidden">
                  <div
                    className="absolute top-0 left-0 h-full bg-pipeline-gradient transition-all duration-1000 ease-out shadow-[0_0_10px_rgba(249,171,255,0.4)]"
                    style={{ width: `${pipelineStage === 0 ? 0 : (pipelineStage / 4) * 100}%` }}
                  />
                </div>

                <div className="w-full grid grid-cols-4 gap-4">
                  {pipelineSteps.map((s, idx) => (
                    <div key={idx} className={`flex flex-col gap-1 ${s.active ? 'opacity-100' : 'opacity-30'}`}>
                      <span className={`text-[10px] font-bold uppercase ${
                        s.active && s.sub !== 'Queued' ? 'text-primary' : 'text-on-surface-variant'
                      }`}>
                        {s.label}
                      </span>
                      <span className="text-xs text-on-surface-variant/80">{s.sub}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Multi-Agent Bidding Grid */}
              {quotes.length > 0 && (
                <div className="bg-surface-container-low border border-outline-variant/10 rounded-2xl p-6 shadow-xl flex flex-col transition-all animate-in fade-in zoom-in duration-700">
                  <div className="flex items-center justify-between mb-6">
                    <div className="flex flex-col">
                      <span className="text-[10px] uppercase font-bold text-secondary tracking-widest mb-1">Comparative Analysis</span>
                      <h2 className="font-headline font-bold text-white tracking-wide">Multi-Agent Bidding</h2>
                    </div>
                    <div className="flex items-center gap-1.5 px-3 py-1 bg-white/5 rounded-full border border-white/10">
                      <span className="text-[10px] font-bold text-on-surface-variant uppercase">{quotes.length} {quotes.length === 1 ? 'Quote' : 'Quotes'}</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {quotes.sort((a, b) => b.score - a.score).map((quote) => (
                      <div
                        key={quote.id}
                        className={`relative flex flex-col p-5 rounded-2xl border transition-all duration-500 ${
                          quote.isWinner
                            ? 'bg-gradient-to-br from-primary/10 to-transparent border-primary/40 shadow-[0_0_20px_rgba(249,171,255,0.1)] scale-105 z-10'
                            : 'bg-[#111111] border-white/5 opacity-70 grayscale-[0.3]'
                        }`}
                      >
                        {quote.isWinner && (
                          <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-primary text-on-primary text-[10px] font-bold px-3 py-1 rounded-full shadow-lg flex items-center gap-1 uppercase tracking-tight">
                            <span className="material-symbols-outlined text-[12px]">award</span>
                            Winner
                          </div>
                        )}
                        <div className="flex flex-col mb-4">
                          <span className={`text-xs font-bold uppercase tracking-widest mb-1 ${quote.isWinner ? 'text-primary' : 'text-on-surface-variant'}`}>{quote.supplier}</span>
                          <div className="flex items-baseline gap-1">
                            <span className="text-3xl font-bold font-headline text-white">{quote.score}</span>
                            <span className="text-[10px] text-on-surface-variant uppercase font-bold">/100</span>
                          </div>
                        </div>
                        <div className="space-y-3 pt-4 border-t border-white/5">
                          <div className="flex justify-between items-center text-xs">
                            <span className="text-on-surface-variant">Price</span>
                            <span className="text-white font-mono font-bold">{quote.price}/unit</span>
                          </div>
                          <div className="flex justify-between items-center text-xs">
                            <span className="text-on-surface-variant">Delivery</span>
                            <span className="text-white font-bold">{quote.delivery}</span>
                          </div>
                          <div className="flex justify-between items-center text-xs">
                            <span className="text-on-surface-variant">Warranty</span>
                            <span className="text-white font-bold">{quote.warranty}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Negotiation Timeline */}
              {negotiations.length > 0 && (
                <div className="bg-surface-container-low border border-outline-variant/10 rounded-2xl p-6 shadow-xl flex flex-col">
                  <div className="flex items-center gap-2 mb-4">
                    <span className="material-symbols-outlined text-primary text-sm">forum</span>
                    <h3 className="text-xs font-bold uppercase tracking-widest text-on-surface-variant/60">Negotiation Timeline</h3>
                    <span className="ml-auto text-[10px] text-on-surface-variant/40">{negotiations.length} messages</span>
                  </div>
                  <div className="flex flex-col gap-2 max-h-[200px] overflow-y-auto scrollbar-hide">
                    {negotiations.map((n, i) => (
                      <div key={i} className={`flex items-start gap-3 text-xs px-3 py-2 rounded-lg ${
                        n.decision === 'ACCEPT' ? 'bg-green-500/5 border border-green-500/10' :
                        n.decision === 'REJECT' ? 'bg-red-500/5 border border-red-500/10' :
                        'bg-white/[0.02] border border-white/5'
                      }`}>
                        <span className={`text-[10px] font-bold uppercase w-16 flex-shrink-0 ${
                          n.decision === 'ACCEPT' ? 'text-green-400' :
                          n.decision === 'REJECT' ? 'text-red-400' :
                          n.decision === 'SENT' ? 'text-blue-400' :
                          'text-yellow-400'
                        }`}>
                          R{n.round} {n.decision}
                        </span>
                        <span className="text-on-surface-variant/70 truncate">{n.message}</span>
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
                          ${log.includes('Error') || log.includes('FAIL') ? 'text-error' : ''}
                          ${log.includes('OK') || log.includes('COMPLETED') ? 'text-secondary font-bold' : ''}
                          ${log.includes('QUOTE') || log.includes('COUNTER') ? 'text-blue-400' : ''}
                          ${log.includes('ACCEPTED') ? 'text-green-400 font-bold' : ''}
                        `}>
                          {log}
                        </span>
                      ))}
                      <div ref={logsEndRef} />
                    </div>
                  )}
                </div>
              </div>

              {/* Error Analysis */}
              {errorAnalysis && (
                <div className="bg-[#1e0a0a] border border-error/20 rounded-2xl p-6 shadow-xl flex flex-col transition-all animate-in fade-in slide-in-from-top-4 duration-500 mt-2">
                  <div className="flex items-center gap-3 mb-4 border-b border-error/10 pb-3">
                    <div className="w-8 h-8 rounded-full bg-error/10 flex items-center justify-center text-error border border-error/20">
                      <span className="material-symbols-outlined text-sm">warning</span>
                    </div>
                    <div>
                      <h3 className="text-error font-bold font-headline tracking-wide">{errorAnalysis.type}</h3>
                      <p className="text-xs text-error/70">{errorAnalysis.details}</p>
                    </div>
                  </div>
                  <div className="bg-[#111111] border border-white/5 rounded-xl p-4">
                    <span className="text-[10px] font-bold uppercase tracking-widest text-primary mb-2 block">Suggested Solution</span>
                    <p className="text-sm text-white/90 leading-relaxed font-body">{errorAnalysis.solution}</p>
                  </div>
                </div>
              )}
            </div>

            {/* Right Column: Live State Profile */}
            <div className="bg-transparent border border-white/5 rounded-3xl overflow-hidden shadow-2xl flex flex-col relative h-full min-h-[500px]">
              {/* Header */}
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

              {/* Ambient Background */}
              <div className="absolute inset-x-0 bottom-0 top-24 overflow-hidden pointer-events-none z-0">
                <div className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full blur-[120px] transition-all duration-1000 ${
                  isRunning ? 'bg-primary/10' : isFinished ? 'bg-secondary/10' : 'bg-transparent'
                }`}></div>
              </div>

              {/* Profile Content */}
              <div className="flex-1 p-8 relative z-10 flex flex-col justify-center">
                {!formData && !isRunning && !isFinished ? (
                  <div className="flex flex-col items-center justify-center text-center text-on-surface-variant/50 h-full">
                    <span className="material-symbols-outlined text-4xl mb-4">account_balance_wallet</span>
                    <p>Fill out the procurement form and deploy the autonomous agent...</p>
                  </div>
                ) : (
                  <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 flex flex-col gap-6">

                    {/* Request Summary */}
                    {formData && (
                      <div className="bg-[#111111] border border-white/5 rounded-2xl p-6">
                        <h4 className="text-white text-sm font-bold uppercase tracking-wider mb-4 flex items-center gap-2">
                          <span className="material-symbols-outlined text-primary text-sm">description</span> Request
                        </h4>
                        <div className="grid grid-cols-2 gap-3 text-xs">
                          <div><span className="text-on-surface-variant">Product</span><br /><span className="text-white font-bold">{formData.item}</span></div>
                          <div><span className="text-on-surface-variant">Quantity</span><br /><span className="text-white font-bold">{formData.quantity}</span></div>
                          <div><span className="text-on-surface-variant">Budget</span><br /><span className="text-secondary font-bold">${formData.budget_usd.toLocaleString()}</span></div>
                          <div><span className="text-on-surface-variant">Deadline</span><br /><span className="text-white font-bold">{formData.deadline}</span></div>
                        </div>
                      </div>
                    )}

                    {/* Active Deal */}
                    {dealDetails.supplier && (
                      <div className="bg-[#111111] border border-white/5 rounded-2xl p-6">
                        <h4 className="text-white text-sm font-bold uppercase tracking-wider mb-6 flex items-center gap-2">
                          <span className="material-symbols-outlined text-primary text-sm">handshake</span> Active Deal
                        </h4>
                        <div className="grid grid-cols-2 gap-4">
                          <div><span className="text-on-surface-variant text-xs">Supplier</span><br /><span className="text-white font-bold text-lg">{dealDetails.supplier}</span></div>
                          <div><span className="text-on-surface-variant text-xs">Total Cost</span><br /><span className="text-secondary font-bold text-lg">{dealDetails.total || dealDetails.amount_usd || 'Computing...'}</span></div>
                          {dealDetails.amount_algo && (
                            <div><span className="text-on-surface-variant text-xs">ALGO Locked</span><br /><span className="text-primary font-mono text-sm">{dealDetails.amount_algo}</span></div>
                          )}
                          {dealDetails.usd_rate && (
                            <div><span className="text-on-surface-variant text-xs">Exchange Rate</span><br /><span className="text-white font-mono text-sm">{dealDetails.usd_rate}</span></div>
                          )}
                          {dealDetails.app_id && (
                            <div><span className="text-on-surface-variant text-xs">App ID</span><br /><span className="text-primary font-mono text-sm">{dealDetails.app_id}</span></div>
                          )}
                          {dealDetails.delivery && (
                            <div><span className="text-on-surface-variant text-xs">Lead Time</span><br /><span className="text-white font-mono text-sm">{dealDetails.delivery}</span></div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Cryptographic Verification */}
                    <div className="bg-gradient-to-br from-white/5 to-transparent border border-white/10 rounded-2xl p-6 backdrop-blur-md">
                      <h4 className="text-white text-sm font-bold uppercase tracking-wider mb-4 border-b border-white/5 pb-2">
                        Cryptographic Verification
                      </h4>
                      <div className="flex flex-col gap-4 mt-4">
                        <div className="flex flex-col break-all">
                          <span className="text-on-surface-variant text-[10px] uppercase mb-1 flex items-center gap-1">
                            <span className="material-symbols-outlined text-[12px]">fingerprint</span> Deal Hash
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

                    {/* Delivery Action */}
                    {isFinished && (
                      <div className="mt-2 text-center animate-pulse">
                        <span className="text-xs text-secondary mb-4 block">Trigger delivery confirmation to release escrowed funds via smart contract.</span>
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

        {/* Agent Pulse */}
        <div className="fixed bottom-12 right-12 hidden lg:flex items-center justify-center bg-surface-container-low/40 backdrop-blur-md p-4 rounded-xl border border-outline-variant/10 z-50">
          <div className="relative">
            <div className="absolute inset-0 rounded-full bg-secondary w-2 h-2 m-auto"></div>
            <div className="w-10 h-10 rounded-full border border-primary/20 animate-pulse opacity-30"></div>
          </div>
          <div className="ml-4">
            <div className="text-[10px] font-bold text-on-surface tracking-widest uppercase">Agent Status</div>
            <div className="text-[10px] text-on-surface-variant/50">{isRunning ? 'Autonomous Mode' : 'Standby'}</div>
          </div>
        </div>
      </main>
    </div>
  );
}
