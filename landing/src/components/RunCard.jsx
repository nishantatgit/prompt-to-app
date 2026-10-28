import { useEffect, useRef, useState } from "react";

// Each step owns an equal share of the pipe. How fast that share fills
// depends on how long the step takes.
const STEPS = [
  { name: "Requirements", detail: "2 explicit, 6 implied", ms: 900 },
  { name: "Architecture", detail: "database, auth, photo storage", ms: 1500 },
  { name: "Build", detail: "passed", ms: 2800 },
  { name: "Tests", detail: "one per acceptance criterion", ms: 2200 },
  { name: "Live at", detail: "marketplace.vyskar.app", ms: 600 },
];

const PROMPT = "A mini marketplace where sellers list items with photos";

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export default function RunCard() {
  const cardRef = useRef(null);
  const fillRef = useRef(null);
  const rafRef = useRef(0);
  const visibleRef = useRef(false);
  const [done, setDone] = useState(0);
  const [lifted, setLifted] = useState(false);

  useEffect(() => {
    const card = cardRef.current;
    if (!card) return undefined;

    const setFill = (percent) => {
      if (fillRef.current) fillRef.current.setAttribute("stroke-dashoffset", String(100 - percent));
    };

    const run = () => {
      cancelAnimationFrame(rafRef.current);
      setDone(0);
      setLifted(false);
      setFill(0);
      const reduced = prefersReducedMotion();
      const start = performance.now();

      const frame = (now) => {
        const elapsed = now - start;
        let finished = 0;
        let stepStart = 0;
        for (const step of STEPS) {
          if (elapsed >= stepStart + step.ms) {
            finished += 1;
            stepStart += step.ms;
          } else {
            break;
          }
        }
        setDone(finished);

        if (finished === STEPS.length) {
          setFill(100);
          setLifted(true);
          return;
        }
        const partial = Math.min(1, (elapsed - stepStart) / STEPS[finished].ms);
        const share = 100 / STEPS.length;
        setFill(reduced ? finished * share : (finished + partial) * share);
        rafRef.current = requestAnimationFrame(frame);
      };
      rafRef.current = requestAnimationFrame(frame);
    };

    if (typeof IntersectionObserver === "undefined") {
      run();
      return () => cancelAnimationFrame(rafRef.current);
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        const visible = entry.isIntersecting;
        if (visible && !visibleRef.current) run();
        if (!visible) cancelAnimationFrame(rafRef.current);
        visibleRef.current = visible;
      },
      { threshold: 0.4 }
    );
    observer.observe(card);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(rafRef.current);
    };
  }, []);

  const finished = done === STEPS.length;

  return (
    <div
      ref={cardRef}
      className={`relative min-w-0 flex-[1_1_420px] rounded-2xl border border-transparent bg-card p-2 ${lifted ? "vy-lift" : ""}`}
    >
      <svg
        aria-hidden="true"
        className="pointer-events-none absolute -top-px -left-px overflow-visible"
        style={{ width: "calc(100% + 2px)", height: "calc(100% + 2px)" }}
      >
        <rect x="0.5" y="0.5" rx="16" ry="16" fill="none" stroke="#3a3768" strokeWidth="1"
          style={{ width: "calc(100% - 1px)", height: "calc(100% - 1px)" }} />
        <rect x="8.5" y="8.5" rx="8" ry="8" fill="none" stroke="#3a3768" strokeWidth="1"
          style={{ width: "calc(100% - 17px)", height: "calc(100% - 17px)" }} />
        <rect ref={fillRef} x="4.5" y="4.5" rx="12" ry="12" pathLength="100" fill="none"
          stroke="#e09a10" strokeWidth="6" strokeDasharray="100" strokeDashoffset="100"
          style={{ width: "calc(100% - 9px)", height: "calc(100% - 9px)" }} />
      </svg>

      <div className="flex items-center justify-between border-b border-line px-[18px] py-3.5 font-mono text-xs">
        <span className="text-dim">example run</span>
        <span className={finished ? "text-saffron" : "text-dim"} aria-live="polite">
          {finished ? "all checks passed" : "running"}
        </span>
      </div>

      <div className="px-[22px] pt-[22px] pb-2">
        <p className="mb-1.5 text-xs tracking-[0.08em] text-dim uppercase">Prompt</p>
        <p className="text-base leading-normal">"{PROMPT}"</p>
      </div>

      <ol aria-label="Run steps" className="flex flex-col gap-1 px-[22px] pt-[18px] pb-6 font-mono text-sm">
        {STEPS.map((step, i) => {
          const isDone = i < done;
          const running = i === done;
          return (
            <li key={step.name}
              className={`flex items-center gap-3 py-2.5 ${i < STEPS.length - 1 ? "border-b border-line-2" : ""}`}>
              {isDone && <Check />}
              {running && <Spinner />}
              {!isDone && !running && <Pending />}
              <span className={`flex-auto ${isDone || running ? "text-fg" : "text-dim"}`}>{step.name}</span>
              <span className={isDone && i === STEPS.length - 1 ? "text-saffron" : "text-dim"}>
                {isDone ? step.detail : running ? "running..." : ""}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function Check() {
  return (
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffb627"
      strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function Spinner() {
  return (
    <svg className="vy-spin" aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none"
      stroke="#ffb627" strokeWidth="2.5" strokeLinecap="round">
      <path d="M21 12a9 9 0 1 1-6.2-8.56" />
    </svg>
  );
}

function Pending() {
  return (
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4a4780" strokeWidth="2">
      <circle cx="12" cy="12" r="8" />
    </svg>
  );
}
