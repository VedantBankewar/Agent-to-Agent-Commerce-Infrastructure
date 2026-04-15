import { Link } from 'react-router-dom';

export default function Header() {
  return (
    <header className="fixed top-0 w-full z-50 bg-black/40 backdrop-blur-2xl border-b border-white/5">
      <div className="flex justify-between items-center px-10 py-6 max-w-screen-2xl mx-auto font-headline font-medium tracking-tight">
        <Link className="text-2xl font-bold text-on-surface tracking-tight hover:text-primary transition-colors duration-300" to="/">AgentTrade</Link>
        <nav className="hidden md:flex items-center gap-10">
          <a className="text-on-surface hover:text-primary transition-colors duration-300 px-4" href="#why-agenttrade">Why AgentTrade</a>
          <a className="text-on-surface hover:text-primary transition-colors duration-300 px-4" href="#solution">Solution</a>
          <a className="text-on-surface hover:text-primary transition-colors duration-300 px-4" href="#features">Features</a>
        </nav>
        <Link className="flex items-center gap-3 bg-surface text-white border border-primary/30 px-8 py-3 rounded-xl font-bold tracking-tight hover:bg-surface-container-low transition-all duration-300 shadow-[0_0_20px_rgba(123,0,143,0.1)] active:scale-95" to="/deploy">
          <span>Deploy Your Agent</span>
          <span className="material-symbols-outlined text-sm">arrow_forward</span>
        </Link>
      </div>
    </header>
  );
}
