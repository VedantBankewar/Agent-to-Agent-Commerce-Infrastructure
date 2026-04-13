import { Brain, BarChart3, ShieldCheck, ArrowRight } from "lucide-react"

const features = [
  {
    icon: Brain,
    title: "Intelligent Automations",
    description:
      "Deploy custom LLM-driven agents that understand market sentiment and news cycles in real-time.",
    color: "primary",
    borderColor: "border-primary",
    href: "#",
    cta: "Explore Agents",
  },
  {
    icon: BarChart3,
    title: "Real-time Analytics",
    description:
      "Zero-latency data pipelines that process millions of signals per second to give you the ultimate edge.",
    color: "tertiary",
    borderColor: "border-tertiary",
    href: "#",
    cta: "View Data Engine",
  },
  {
    icon: ShieldCheck,
    title: "Secure Execution",
    description:
      "Military-grade encryption and non-custodial architecture ensure your capital remains entirely under your control.",
    color: "secondary",
    borderColor: "border-secondary",
    href: "#",
    cta: "Security Audit",
  },
]

const colorClasses = {
  primary: {
    bg: "bg-primary-container/20",
    text: "text-primary",
    hover: "group-hover:translate-x-2",
  },
  tertiary: {
    bg: "bg-tertiary/10",
    text: "text-tertiary",
    hover: "group-hover:translate-x-2",
  },
  secondary: {
    bg: "bg-secondary/10",
    text: "text-secondary",
    hover: "group-hover:translate-x-2",
  },
}

export function Features() {
  return (
    <section className="py-32 px-6 bg-surface-container-low">
      <div className="max-w-7xl mx-auto">
        {/* Section Header */}
        <div className="mb-20 text-center space-y-4">
          <h2 className="text-4xl md:text-5xl font-extrabold font-headline tracking-tight text-on-surface">
            Designed for Sovereignty
          </h2>
          <p className="text-on-surface-variant max-w-2xl mx-auto">
            Our infrastructure is built to empower traders with tools previously
            reserved for institutional titans.
          </p>
        </div>

        {/* Features Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {features.map((feature) => {
            const Icon = feature.icon
            const colors = colorClasses[feature.color as keyof typeof colorClasses]

            return (
              <a
                key={feature.title}
                href={feature.href}
                className={`group p-8 rounded-3xl bg-surface transition-all duration-500 hover:bg-surface-container-high border-b-4 border-transparent hover:${feature.borderColor}`}
              >
                {/* Icon */}
                <div
                  className={`w-14 h-14 rounded-2xl ${colors.bg} flex items-center justify-center mb-8 group-hover:scale-110 transition-transform`}
                >
                  <Icon
                    className={`w-7 h-7 ${colors.text}`}
                    style={{ fill: "currentColor" }}
                  />
                </div>

                {/* Title */}
                <h3 className="text-2xl font-bold font-headline mb-4 text-on-surface">
                  {feature.title}
                </h3>

                {/* Description */}
                <p className="text-on-surface-variant leading-relaxed mb-6 font-body">
                  {feature.description}
                </p>

                {/* CTA */}
                <div
                  className={`flex items-center gap-2 ${colors.text} font-bold text-sm cursor-pointer ${colors.hover} transition-transform`}
                >
                  {feature.cta}
                  <ArrowRight className="w-4 h-4" />
                </div>
              </a>
            )
          })}
        </div>
      </div>
    </section>
  )
}
