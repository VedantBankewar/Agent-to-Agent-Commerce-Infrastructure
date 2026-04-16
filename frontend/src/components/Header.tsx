import { Link, useLocation } from 'react-router-dom';

function NavLink({ to, children, className }: { to: string; children: React.ReactNode; className?: string }) {
  const { pathname } = useLocation();
  const isHome = pathname === '/';
  const hash = to.split('#')[1];

  if (isHome && hash) {
    return (
      <a
        href={`#${hash}`}
        className={className}
        onClick={(e) => {
          e.preventDefault();
          document.getElementById(hash)?.scrollIntoView({ behavior: 'smooth' });
          window.history.pushState(null, '', `#${hash}`);
        }}
      >
        {children}
      </a>
    );
  }

  return <Link to={to} className={className}>{children}</Link>;
}

export default function Header() {
  return (
    <header className="fixed top-0 w-full z-50 bg-black/40 backdrop-blur-2xl border-b border-white/5">
      <div className="flex justify-between items-center px-10 py-4 max-w-screen-2xl mx-auto font-headline font-medium tracking-tight">
        <NavLink
          className="text-2xl font-bold text-on-surface tracking-tight hover:text-primary transition-colors duration-300"
          to="/#hero"
        >
          AgentTrade
        </NavLink>
        <nav className="hidden md:flex items-center gap-10">
          <NavLink className="text-on-surface hover:text-primary transition-colors duration-300 px-4" to="/#why-agenttrade">Why AgentTrade</NavLink>
          <NavLink className="text-on-surface hover:text-primary transition-colors duration-300 px-4" to="/#solution">Solution</NavLink>
          <NavLink className="text-on-surface hover:text-primary transition-colors duration-300 px-4" to="/#features">Features</NavLink>
        </nav>
        <Link className="flex items-center gap-3 bg-surface text-white border border-primary/30 px-8 py-3 rounded-xl font-bold tracking-tight hover:bg-surface-container-low transition-all duration-300 shadow-[0_0_20px_rgba(123,0,143,0.1)] active:scale-95" to="/deploy">
          <span>Deploy Your Agent</span>
          <span className="material-symbols-outlined text-sm">arrow_forward</span>
        </Link>
      </div>
    </header>
  );
} 
