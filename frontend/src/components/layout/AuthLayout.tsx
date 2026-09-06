import { ChefHat } from 'lucide-react'
import type { ReactNode } from 'react'

const STEPS = [
  'Rate five recipes you know',
  'The model builds your taste profile',
  'Recommendations sharpen with every rating',
] as const

interface AuthLayoutProps {
  children: ReactNode
}

/**
 * Split layout for login and register: a green brand panel from `lg` up, the
 * form centred beside it. Below `lg` the panel is dropped entirely so the form
 * gets the whole screen.
 */
export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="flex min-h-dvh bg-background">
      <aside
        className="relative hidden w-[44%] max-w-[620px] flex-col overflow-hidden p-14 lg:flex"
        style={{
          backgroundImage:
            'linear-gradient(150deg, #47AE55 0%, #3FA34D 42%, #2C7539 100%)',
        }}
      >
        <div className="flex items-center gap-3">
          <span className="flex size-9 items-center justify-center rounded-[11px] bg-white/20 text-white">
            <ChefHat className="size-5" />
          </span>
          <span className="text-[19px] font-extrabold tracking-[-0.03em] text-white">
            FoodRec
          </span>
        </div>

        <div className="mt-20">
          <h1 className="text-[40px] leading-[1.12] font-extrabold tracking-[-0.04em] text-balance text-white">
            Recipes picked for the way you actually cook.
          </h1>
          <p className="mt-5 max-w-[440px] text-base leading-relaxed text-white/80">
            Rate a handful of dishes and the model learns your taste from
            230,000 recipes. No meal plans, no lectures, just the next thing
            worth cooking.
          </p>
        </div>

        <ol className="mt-11 flex flex-col gap-4">
          {STEPS.map((step, index) => (
            <li key={step} className="flex items-center gap-3.5">
              <span className="flex size-[26px] shrink-0 items-center justify-center rounded-full bg-white/20 text-xs font-extrabold text-white">
                {index + 1}
              </span>
              <span className="text-[15px] font-semibold text-white/90">
                {step}
              </span>
            </li>
          ))}
        </ol>

        <div className="grow" />

        <p className="text-xs leading-relaxed text-white/60">
          Recipe data from the Food.com dataset on Kaggle.
        </p>
      </aside>

      <main className="flex flex-1 items-center justify-center px-4 py-12 sm:px-8">
        <div className="w-full max-w-[380px]">{children}</div>
      </main>
    </div>
  )
}
