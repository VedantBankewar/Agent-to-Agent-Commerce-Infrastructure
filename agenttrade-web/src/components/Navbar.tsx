import { Button } from "@/components/ui/button"
import { Menu, X } from "lucide-react"
import { useState } from "react"

const navLinks = [
  { label: "Platform", href: "#", active: true },
  { label: "Agents", href: "#", active: false },
  { label: "Intelligence", href: "#", active: false },
  { label: "Pricing", href: "#", active: false },
]

export function Navbar() {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <nav className="fixed top-0 w-full z-50 bg-surface/80 backdrop-blur-xl shadow-[0_20px_50px_rgba(249,171,255,0.06)]">
      <div className="flex justify-between items-center max-w-7xl mx-auto px-6 h-20">
        {/* Logo */}
        <div className="text-xl font-bold tracking-tighter text-primary font-headline">
          AgentTrade
        </div>

        {/* Desktop Nav */}
        <div className="hidden md:flex items-center gap-8">
          {navLinks.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className={`text-sm font-semibold tracking-tight transition-colors ${
                link.active
                  ? "text-primary border-b-2 border-primary pb-1"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              {link.label}
            </a>
          ))}
        </div>

        {/* Desktop Actions */}
        <div className="hidden md:flex items-center gap-4">
          <button className="text-slate-400 hover:text-white transition-colors text-sm tracking-tight">
            Login
          </button>
          <Button size="lg" className="rounded-full">
            Launch Terminal
          </Button>
        </div>

        {/* Mobile Menu Toggle */}
        <button
          className="md:hidden text-slate-400 hover:text-white"
          onClick={() => setMobileOpen(!mobileOpen)}
        >
          {mobileOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Mobile Menu */}
      {mobileOpen && (
        <div className="md:hidden bg-surface border-t border-outline-variant/20">
          <div className="flex flex-col p-6 gap-4">
            {navLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className={`text-base font-semibold py-2 ${
                  link.active ? "text-primary" : "text-slate-400"
                }`}
              >
                {link.label}
              </a>
            ))}
            <hr className="border-outline-variant/20" />
            <button className="text-slate-400 text-left py-2">Login</button>
            <Button size="lg" className="rounded-full w-full">
              Launch Terminal
            </Button>
          </div>
        </div>
      )}
    </nav>
  )
}
