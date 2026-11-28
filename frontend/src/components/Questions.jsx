import { useEffect, useRef, useState } from 'react'
import { scrollBehavior } from '../lib/motion.js'

export const NOT_SURE = "I'm not sure"

// One or two quick questions before building. Each answer is a tap; "I'm not
// sure" leaves the choice to Vyskar. Build starts once all are answered.
export default function Questions({ questions, onDone, onSkip, running }) {
  const [answers, setAnswers] = useState({})
  const heading = useRef(null)

  // Bring the questions into view, and to screen readers, as they appear.
  useEffect(() => {
    heading.current?.scrollIntoView({ behavior: scrollBehavior(), block: 'center' })
    heading.current?.focus({ preventScroll: true })
  }, [])
  const answered = questions.every((_, i) => answers[i])

  function pick(i, answer) {
    setAnswers((a) => ({ ...a, [i]: answer }))
  }

  return (
    <section aria-labelledby="questions-title" className="voice-fade-in flex flex-col gap-5 rounded-2xl border border-line bg-card p-6">
      <div>
        <h2 id="questions-title" ref={heading} tabIndex={-1} className="font-display text-lg font-bold outline-none">
          {questions.length === 1 ? 'One quick question' : 'Two quick questions'}
        </h2>
        <p className="mt-1 text-sm text-muted">So Vyskar builds the right thing.</p>
      </div>
      {questions.map((q, i) => (
        <fieldset key={q.question} className="flex flex-col gap-3">
          <legend className="mb-3 font-semibold">{q.question}</legend>
          <div className="flex flex-wrap gap-2">
            {[...q.options, NOT_SURE].map((option) => {
              const chosen = answers[i] === option
              return (
                <button
                  key={option}
                  type="button"
                  aria-pressed={chosen}
                  onClick={() => pick(i, option)}
                  className={`min-h-11 rounded-full border px-4 text-sm ${
                    chosen
                      ? 'border-accent bg-accent font-semibold text-on-accent'
                      : option === NOT_SURE
                        ? 'border-wall text-dim hover:text-fg'
                        : 'border-wall text-fg hover:border-accent'
                  }`}
                >
                  {option}
                </button>
              )
            })}
          </div>
        </fieldset>
      ))}
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => onDone(questions.map((q, i) => ({ question: q.question, answer: answers[i] })))}
          disabled={!answered || running}
          className="min-h-12 rounded-full bg-accent px-7 font-semibold text-on-accent disabled:cursor-not-allowed disabled:opacity-50"
        >
          {running ? 'Building...' : 'Build it'}
        </button>
        <button type="button" onClick={onSkip} disabled={running} className="min-h-11 px-2 text-sm text-muted underline underline-offset-4 disabled:opacity-50">
          Skip, just build
        </button>
      </div>
    </section>
  )
}
