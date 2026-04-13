import { Button } from "@/components/ui/button"

const avatars = [
  "https://lh3.googleusercontent.com/aida-public/AB6AXuDhn75sEBYErYVMQ0ljcCdztXkgjT-J1dGO3-hPdRsw1_6ERGiSOUhLxwmkprbe7xvXUn_JjKPrG_pNkz_ZQD6Qvl06AdPJi1h2qfT1vPN4dHXjjm_mAJvSUqxZ_AjfSCDx0udM6wmJhhkGCv6Pejo4IOyrFpYNDaoJLjmK9DShIuZ9-YIaLoH3yHP2qqd3PGIAOpWb37i8UNfV-u9C71Gk5qyFf6fTwTjmR5MybNKsNzwC4CCFDJzw5lRV-knSmIjCrxK8FN6o8LS1",
  "https://lh3.googleusercontent.com/aida-public/AB6AXuDR2gouJKqowmYFZD0I5tW_6qJezmbMDLCIOjkoFdBCdvpWovh6eX7ZIjQjFJszs0guIGRwRXTKWhNfQy-80sQVCp9D9nlwtxaQ3KBCMlnj_J0PXARIFNzJb-YjdCLTOhKze3UeWF2l3-QqV_1st8vZk5YHuvw5IJNTksOFxUl9Lt9a3z0iqFAIit1f8AGHGzgsU1WuCQ_dj9Gg4eZgMBHKECBH7yjjNqmmSbAa277xXOSxSejReE34c8vFPb0rPjIEbZycylO5Dv5Z",
  "https://lh3.googleusercontent.com/aida-public/AB6AXuCDZLDvhCj5efVuMKpYzs0moavgnd5nj5vPeYU3ohNTt7rVbPLOKOJSQjceOi78vNSqwY5-NNt_T0hzwQb7A1p2Stm4zkEyiPjvf8SiFE8AH15ssTa446NjhjyBX91gqrgudzhyoY2nWKlSgNysGIsebFyJUjBVIhHjCrWs1i4iNrvaN08yrU-UdktR4I2ALt8c9jaRQIO2uwTH65OZKe1zU7tnG_pwZPn4lGPbu1XGzcCH9HuCZlcwP8G5-MiNBe9mV0WpGiR-xudQ",
]

export function CTASection() {
  return (
    <section className="py-24 px-6">
      <div className="max-w-7xl mx-auto">
        <div
          className="rounded-[2.5rem] bg-gradient-to-br from-surface-container-high to-surface-container-lowest p-12 md:p-20 relative overflow-hidden text-center"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100'%3E%3Crect width='100' height='100' fill='%231a1a1a'/%3E%3C/svg%3E")`,
          }}
        >
          {/* Carbon fiber overlay */}
          <div
            className="absolute inset-0 opacity-10"
            style={{
              backgroundImage: `url("https://www.transparenttextures.com/patterns/carbon-fibre.png")`,
            }}
          />

          <div className="relative z-10 space-y-8">
            {/* Headline */}
            <h2 className="text-5xl md:text-6xl font-extrabold font-headline tracking-tighter text-on-surface">
              Ready to evolve?
            </h2>

            {/* Subtext */}
            <p className="text-on-surface-variant text-xl max-w-xl mx-auto">
              Join 50,000+ traders already building the future of decentralized
              finance with AgentTrade.
            </p>

            {/* CTA Row */}
            <div className="flex flex-col sm:flex-row justify-center items-center gap-6 pt-8">
              {/* Avatar Stack */}
              <div className="flex -space-x-4">
                {avatars.map((src, i) => (
                  <img
                    key={i}
                    src={src}
                    alt={`User ${i + 1}`}
                    className="w-12 h-12 rounded-full border-4 border-surface object-cover"
                  />
                ))}
                <div className="w-12 h-12 rounded-full border-4 border-surface bg-primary-container flex items-center justify-center text-[10px] font-bold text-on-primary-container">
                  +10k
                </div>
              </div>

              {/* CTA Button */}
              <Button size="xl" className="rounded-full shadow-xl shadow-primary/20">
                Start Trading Now
              </Button>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
