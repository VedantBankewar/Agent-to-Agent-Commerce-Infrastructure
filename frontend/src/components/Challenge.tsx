export default function Challenge() {
  return (
    <section className="min-h-screen flex items-center justify-center px-10 bg-[#0e0e0e] relative overflow-hidden py-32 pt-40" id="why-agenttrade">
      <div className="max-w-screen-2xl w-full relative z-10">
        <div className="mb-16">
          <span className="text-primary font-label text-xs font-bold uppercase tracking-[0.3em] mb-4 block">The Challenge</span>
          <h2 className="text-5xl md:text-7xl font-headline font-bold text-on-background tracking-tight">Traditional Commerce is Broken</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="glass-panel rounded-[2rem] p-10 hover:border-primary/30 transition-all duration-500 group">
            <div className="text-5xl font-headline font-extrabold text-primary/30 group-hover:text-primary/60 transition-colors mb-10">01</div>
            <h3 className="text-2xl font-headline font-bold text-on-background mb-4">Manual Inefficiency</h3>
            <p className="text-on-surface-variant leading-relaxed">Procurement teams spend 60% of their time on repetitive supplier discovery and price comparisons.</p>
          </div>
          <div className="glass-panel rounded-[2rem] p-10 hover:border-primary/30 transition-all duration-500 group">
            <div className="text-5xl font-headline font-extrabold text-primary/30 group-hover:text-primary/60 transition-colors mb-10">02</div>
            <h3 className="text-2xl font-headline font-bold text-on-background mb-4">Slow Settlement</h3>
            <p className="text-on-surface-variant leading-relaxed">Traditional payment rails take 30-90 days, locking capital and creating friction in supply chains.</p>
          </div>
          <div className="glass-panel rounded-[2rem] p-10 hover:border-primary/30 transition-all duration-500 group">
            <div className="text-5xl font-headline font-extrabold text-primary/30 group-hover:text-primary/60 transition-colors mb-10">03</div>
            <h3 className="text-2xl font-headline font-bold text-on-background mb-4">Limited Scale</h3>
            <p className="text-on-surface-variant leading-relaxed">Human-driven negotiations can't scale to match the velocity of modern digital commerce.</p>
          </div>
        </div>
      </div>
      <div className="absolute -bottom-24 -right-24 w-96 h-96 bg-primary/5 blur-[120px] rounded-full"></div>
    </section>
  );
}
