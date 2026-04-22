import { Link } from 'react-router-dom';

export default function Hero() {
  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center pt-24 overflow-hidden" id="hero">
      <div className="absolute inset-0 z-0 overflow-hidden">
        <div className="absolute inset-0 z-0">
          <img alt="Background" className="w-full h-full object-cover opacity-40 mix-blend-lighten" src="https://lh3.googleusercontent.com/aida/ADBb0uj_QZGGe1cNI6BxUs3ToOEWJX7Y_5wmkv_Po9nNIfVygt6qcP53x6mypCgvjT8u2W-mgN-7XDZsbLZCjqCDwvozEsEJY0_912sHapOPJf-wgMlerfPmO8jNNNuqqmCauQ2RcX8yaWF5Z--PBY43gp5af6FyIzCXeHe7gx0va0P4KRpMZpKLfv9KSEOkByBkvvYGiR9Xn-B4O9-o95HnNDvrxCtazdnHZrVQg2VU64M-kt3Fi3OxEutOFmoVOmsdts17I_RQhvN4DA" style={{ maskImage: "radial-gradient(circle at center, black 30%, transparent 80%)" }} />
        </div>
        <div className="absolute inset-0 z-10 bg-radial-gradient from-primary/10 via-transparent to-transparent opacity-50"></div>
      </div>
      <div className="relative z-10 max-w-5xl px-10 text-center">
        <div className="inline-flex items-center gap-2 px-6 py-2 rounded-full bg-white/5 border border-white/10 text-on-surface-variant mb-10 backdrop-blur-md">
          <span className="text-xs font-label font-bold uppercase tracking-[0.3em]">AUTONOMOUS AI COMMERCE</span>
        </div>
        <h1 className="text-6xl md:text-9xl font-headline font-extrabold tracking-tighter text-on-background mb-8 leading-[1]">Autonomous Agent-to-Agent <br /> <span className="text-transparent bg-clip-text bg-gradient-to-b from-white via-primary to-primary-container drop-shadow-[0_0_30px_rgba(249,171,255,0.4)]">Commerce Infrastructure</span></h1>
        <p className="text-lg md:text-xl text-on-surface-variant/80 max-w-2xl mx-auto mb-14 font-body font-light leading-relaxed">Autonomous AI procurement agents that discover suppliers, negotiate deals, and settle payments on the Algorand blockchain — without any human in the loop.</p>
        <div className="flex flex-col md:flex-row gap-4 justify-center items-center">
          <Link className="bg-white text-black px-12 py-4 rounded-lg text-lg font-bold hover:bg-on-surface transition-all shadow-[0_0_40px_rgba(255,255,255,0.15)] flex items-center justify-center" to="/deploy">
            <span>Deploy Your Agent</span>
            <span className="material-symbols-outlined ml-2 text-sm">arrow_forward</span>
          </Link>
          <a
            href="https://github.com/VedantBankewar/Agent-to-Agent-Commerce-Infrastructure#readme"
            target="_blank"
            rel="noopener noreferrer"
            className="bg-white/5 border border-white/10 text-on-surface px-12 py-4 rounded-lg text-lg font-bold backdrop-blur-md hover:bg-white/10 transition-all flex items-center justify-center"
          >
            View Documentation
          </a>
        </div>
      </div>
    </section>
  );
}
