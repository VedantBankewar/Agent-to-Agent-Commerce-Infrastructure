import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full font-bold text-sm transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary:
          "bg-gradient-to-br from-primary to-primary-container text-on-primary hover:scale-105 shadow-lg shadow-primary/20",
        secondary:
          "border border-outline-variant text-on-surface hover:bg-surface-bright",
        ghost:
          "text-slate-400 hover:text-white",
        tertiary:
          "text-tertiary hover:text-tertiary/80",
      },
      size: {
        default: "px-6 py-2.5",
        lg: "px-10 py-4 text-lg rounded-xl",
        xl: "px-12 py-4 text-lg rounded-full",
        icon: "p-2.5",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
