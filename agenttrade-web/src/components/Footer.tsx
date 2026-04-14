import { FileText, Shield, Scale } from "lucide-react"

const footerLinks = {
  resources: [
    { label: "API Documentation", href: "#", icon: FileText },
    { label: "Security", href: "#", icon: Shield },
  ],
  legal: [
    { label: "Privacy Policy", href: "#", icon: Scale },
    { label: "Terms of Service", href: "#", icon: FileText },
  ],
}

export function Footer() {
  return (
    <footer className="bg-surface-container-low w-full py-12 px-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-7xl mx-auto">
        {/* Brand Column */}
        <div className="space-y-6">
          <div className="text-lg font-bold text-primary font-headline">
            AgentTrade AI
          </div>
          <p className="text-slate-500 text-sm max-w-xs font-body">
            Autonomous intelligence for the decentralized global markets. Powering
            the next generation of financial sovereignty.
          </p>
          <div className="text-xs text-slate-500 font-manrope">
            © 2024 AgentTrade AI. The Kinetic Luminary.
          </div>
        </div>

        {/* Links Grid */}
        <div className="grid grid-cols-2 gap-8">
          {/* Resources */}
          <div className="space-y-4">
            <h4 className="text-on-surface font-bold text-xs uppercase tracking-widest">
              Resources
            </h4>
            <div className="flex flex-col gap-3">
              {footerLinks.resources.map((link) => (
                <a
                  key={link.label}
                  href={link.href}
                  className="text-slate-500 hover:text-primary transition-colors font-manrope text-xs opacity-80 hover:opacity-100 flex items-center gap-2"
                >
                  <link.icon className="w-3 h-3" />
                  {link.label}
                </a>
              ))}
            </div>
          </div>

          {/* Legal */}
          <div className="space-y-4">
            <h4 className="text-on-surface font-bold text-xs uppercase tracking-widest">
              Legal
            </h4>
            <div className="flex flex-col gap-3">
              {footerLinks.legal.map((link) => (
                <a
                  key={link.label}
                  href={link.href}
                  className="text-slate-500 hover:text-primary transition-colors font-manrope text-xs opacity-80 hover:opacity-100 flex items-center gap-2"
                >
                  <link.icon className="w-3 h-3" />
                  {link.label}
                </a>
              ))}
            </div>
          </div>
        </div>
      </div>
    </footer>
  )
}
