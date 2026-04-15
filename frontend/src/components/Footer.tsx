export default function Footer() {
  return (
    <footer className="w-full bg-[#131313] border-t border-[#e5e2e1]/10 font-body text-sm">
      <div className="max-w-7xl mx-auto px-12 py-20 flex flex-col md:flex-row justify-between items-start gap-12 md:gap-32">
        <div className="flex-1 space-y-6">
          <div className="text-lg font-black text-[#e5e2e1]">AgentTrade</div>
          <p className="text-[#c8c8b0] max-w-xs leading-relaxed">
            Building the autonomous commerce layer for the agent economy.
          </p>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-12 md:gap-24 flex-[2]">
          <div className="space-y-4">
            <h4 className="text-white font-bold uppercase tracking-wider text-xs">Product</h4>
            <ul className="space-y-3">
              <li><a className="text-[#c8c8b0] hover:text-[#f9abff] transition-opacity" href="#features">Features</a></li>
              <li><a className="text-[#c8c8b0] hover:text-[#f9abff] transition-opacity" href="https://github.com/VedantBankewar/Agent-to-Agent-Commerce-Infrastructure" target="_blank" rel="noopener noreferrer">Documentation</a></li>
              <li><a className="text-[#c8c8b0] hover:text-[#f9abff] transition-opacity" href="#">Pricing</a></li>
              <li><a className="text-[#c8c8b0] hover:text-[#f9abff] transition-opacity" href="#">API Reference</a></li>
            </ul>
          </div>
          <div className="space-y-4">
            <h4 className="text-white font-bold uppercase tracking-wider text-xs">Company</h4>
            <ul className="space-y-3">
              <li><a className="text-[#c8c8b0] hover:text-[#f9abff] transition-opacity" href="#">About</a></li>
              <li><a className="text-[#c8c8b0] hover:text-[#f9abff] transition-opacity" href="#">Blog</a></li>
              <li><a className="text-[#c8c8b0] hover:text-[#f9abff] transition-opacity" href="#">Careers</a></li>
              <li><a className="text-[#c8c8b0] hover:text-[#f9abff] transition-opacity" href="#">Contact</a></li>
            </ul>
          </div>
          <div className="space-y-4">
            <h4 className="text-white font-bold uppercase tracking-wider text-xs">Resources</h4>
            <ul className="space-y-3">
              <li><a className="text-[#c8c8b0] hover:text-[#f9abff] transition-opacity" href="#">Whitepaper</a></li>
              <li><a className="text-[#c8c8b0] hover:text-[#f9abff] transition-opacity" href="#">Developer Docs</a></li>
              <li><a className="text-[#c8c8b0] hover:text-[#f9abff] transition-opacity" href="#">Community</a></li>
              <li><a className="text-[#c8c8b0] hover:text-[#f9abff] transition-opacity" href="#">Support</a></li>
            </ul>
          </div>
        </div>
      </div>
      <div className="max-w-7xl mx-auto px-12 py-8 border-t border-[#e5e2e1]/10 flex flex-col md:flex-row justify-between items-center gap-4">
        <div className="text-[#c8c8b0]/60">
          © 2026 AgentTrade. All rights reserved.
        </div>
      </div>
    </footer>
  );
}
