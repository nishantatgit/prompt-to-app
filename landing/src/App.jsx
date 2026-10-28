import RunCard from "./components/RunCard.jsx";

const REPO_URL = "https://github.com/nishantatgit/prompt-to-app";
const X_URL = "https://x.com/NiVaCo5";

const STEPS = [
  { n: "01", title: "Understand", body: "Your words become a numbered list of requirements, each one quoting what you asked for." },
  { n: "02", title: "Design", body: "An architecture where every feature traces back to a requirement, with acceptance criteria for each." },
  { n: "03", title: "Build", body: "A React app written to that design, compiled and fixed until the build passes." },
  { n: "04", title: "Prove", body: "Browser tests run against every acceptance criterion, and you get the report with the app." },
];

const REASONS = [
  {
    title: "Every requirement traced",
    body: "Each feature points to the requirement it fulfils, and each test points to the criterion it proves. If something is missing, you see where.",
    icon: (
      <>
        <path d="M9 11l3 3L22 4" />
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
      </>
    ),
  },
  {
    title: "A test report you can read",
    body: 'Plain language results for every check, with a replay of any failure. No black box, no "trust me".',
    icon: (
      <>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="8" y1="13" x2="16" y2="13" />
        <line x1="8" y1="17" x2="13" y2="17" />
      </>
    ),
  },
  {
    title: "Your key, your app",
    body: "Bring your own Anthropic or OpenAI key and see exactly how many tokens every build used.",
    icon: (
      <>
        <circle cx="8" cy="15" r="4" />
        <line x1="10.85" y1="12.15" x2="19" y2="4" />
        <line x1="18" y1="5" x2="20" y2="7" />
        <line x1="15" y1="8" x2="17" y2="10" />
      </>
    ),
  },
];

const LEVELS = [
  ["Level 1: Simple pages", 5],
  ["Level 2: Data in the browser", 5],
  ["Level 3: Database apps", 6],
  ["Level 4: Login and accounts", 5],
  ["Level 5: Hard", 4],
];

// Replace with the measured weekly score.
const SCORE = "[SCORE]";

const primaryButton =
  "inline-flex min-h-11 items-center rounded-full bg-saffron font-semibold text-on-saffron no-underline hover:text-on-saffron hover:brightness-105";

function Eyebrow({ children }) {
  return <p className="font-mono text-[13px] tracking-[0.08em] text-saffron uppercase">{children}</p>;
}

function SectionTitle({ children }) {
  return (
    <h2 className="font-display text-[clamp(26px,3.4vw,40px)] leading-[1.15] font-bold tracking-[-0.01em]">
      {children}
    </h2>
  );
}

export default function App() {
  return (
    <div className="min-h-screen bg-ink text-fg">
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-4 px-6 py-5">
          <a href="#top" className="font-display text-xl font-bold tracking-[0.1em] text-fg no-underline">
            VYSKAR
          </a>
          <nav aria-label="Main" className="flex flex-wrap items-center gap-7 text-[15px]">
            <a href="#how" className="text-muted no-underline">How it works</a>
            <a href="#proof" className="text-muted no-underline">Why Vyskar</a>
            <a href="#benchmark" className="text-muted no-underline">Benchmark</a>
            <a href="#start" className={`${primaryButton} px-5 py-3`}>Hire your senior engineer</a>
          </nav>
        </div>
      </header>

      <main>
        <section id="top" className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-14 px-6 pt-24 pb-22">
          <div className="flex min-w-0 flex-[1_1_480px] flex-col gap-7">
            <Eyebrow>From prompt to app</Eyebrow>
            <h1 className="font-display text-[clamp(34px,4.6vw,56px)] leading-[1.1] font-bold tracking-[-0.02em]">
              You're the architect. Vyskar is your senior engineer.
            </h1>
            <p className="max-w-[34em] text-xl leading-[1.55] text-muted">
              Describe the app you want in plain English. Vyskar turns it into requirements, designs it, writes the
              code, and tests every requirement before you see it.
            </p>
            <div className="flex flex-wrap gap-3.5 pt-1">
              <a href="#start" className={`${primaryButton} px-[26px] py-[15px] text-base`}>Hire your senior engineer</a>
              <a href="#benchmark"
                className="inline-flex min-h-11 items-center rounded-full border border-wall px-[26px] py-[15px] text-base font-medium text-fg no-underline">
                See the benchmark
              </a>
            </div>
            <p className="text-sm text-dim">Free with your own Anthropic or OpenAI key.</p>
          </div>
          <RunCard />
        </section>

        <section id="how" className="border-t border-line bg-ink-2">
          <div className="mx-auto flex max-w-[1200px] flex-col gap-12 px-6 py-24">
            <div className="flex max-w-[760px] flex-col gap-3.5">
              <Eyebrow>How it works</Eyebrow>
              <SectionTitle>Let the senior engineer work for you.</SectionTitle>
              <p className="text-lg leading-relaxed text-muted">
                Not one giant guess. Four steps, each checked before the next one starts.
              </p>
            </div>
            <div className="flex flex-wrap gap-5">
              {STEPS.map((s) => (
                <div key={s.n} className="flex min-w-0 flex-[1_1_240px] flex-col gap-3.5 rounded-2xl border border-line bg-card p-7">
                  <span className="font-mono text-[13px] text-saffron">{s.n}</span>
                  <h3 className="font-display text-[19px] font-medium">{s.title}</h3>
                  <p className="text-[15px] leading-relaxed text-muted">{s.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="proof" className="border-t border-line">
          <div className="mx-auto flex max-w-[1200px] flex-col gap-12 px-6 py-24">
            <div className="flex max-w-[760px] flex-col gap-3.5">
              <Eyebrow>Why Vyskar</Eyebrow>
              <SectionTitle>Exactly what you asked for. Nothing you didn't.</SectionTitle>
            </div>
            <div className="flex flex-wrap gap-5">
              {REASONS.map((r) => (
                <div key={r.title} className="flex min-w-0 flex-[1_1_300px] flex-col gap-4 py-1">
                  <svg aria-hidden="true" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#ffb627"
                    strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    {r.icon}
                  </svg>
                  <h3 className="font-display text-[19px] font-medium">{r.title}</h3>
                  <p className="text-base leading-relaxed text-muted">{r.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="benchmark" className="border-t border-line bg-ink-2">
          <div className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-14 px-6 py-24">
            <div className="flex min-w-0 flex-[1_1_420px] flex-col gap-[18px]">
              <Eyebrow>Built in public</Eyebrow>
              <SectionTitle>Measured, not promised.</SectionTitle>
              <p className="text-lg leading-relaxed text-muted">
                Vyskar is scored every week against a fixed benchmark of 25 apps, from a tip calculator to a live chat
                room. The prompts never change, so the score means something.
              </p>
              <a href={REPO_URL} className="text-base font-medium text-fg">Follow the build on GitHub</a>
            </div>
            <div className="flex min-w-0 flex-[1_1_420px] flex-col gap-1.5 rounded-2xl border border-line bg-card p-7">
              <div className="flex items-baseline justify-between gap-4 border-b border-line pb-[18px]">
                <span className="text-[15px] text-muted">This week's score</span>
                <span className="font-display text-[34px] font-bold text-saffron">{SCORE}/25</span>
              </div>
              <ol aria-label="Benchmark levels" className="flex flex-col">
                {LEVELS.map(([label, count], i) => (
                  <li key={label}
                    className={`flex justify-between gap-4 py-3.5 text-[15px] ${i < LEVELS.length - 1 ? "border-b border-line-2" : ""}`}>
                    <span>{label}</span>
                    <span className="font-mono text-dim">{count} apps</span>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </section>

        <section id="start" className="border-t border-line">
          <div className="mx-auto flex max-w-[1200px] flex-col items-center gap-6 px-6 py-28 text-center">
            <h2 className="max-w-[16em] font-display text-[clamp(30px,4.4vw,50px)] leading-[1.12] font-bold tracking-[-0.02em]">
              From prompt to app. Tested before you see it.
            </h2>
            <p className="max-w-[32em] text-lg leading-relaxed text-muted">
              Tell Vyskar what you need. It handles the requirements, the code and the testing.
            </p>
            <a href="#top" className={`${primaryButton} px-8 py-[17px] text-[17px]`}>Hire your senior engineer</a>
          </div>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-4 px-6 py-7 text-sm text-dim">
          <span className="font-display font-bold tracking-[0.1em] text-fg">VYSKAR</span>
          <div className="flex flex-wrap gap-6">
            <a href={X_URL} className="text-muted no-underline">Follow on X</a>
            <a href={REPO_URL} className="text-muted no-underline">GitHub</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
