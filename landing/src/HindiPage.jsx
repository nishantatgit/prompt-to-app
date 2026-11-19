import { useEffect, useState } from "react";

// Hindi landing page: one line, "बोलो, और ऐप बन जाएगा", and an animation of
// the same idea. A voice waveform plays, its bars morph into the blocks of an
// app screen, a phone draws itself around them, and the Vyskar tick appears.

const LINE_1 = "बोलो,";
const LINE_2 = "और ऐप बन जाएगा";

// Timeline in milliseconds. The whole sequence loops every LOOP ms.
const SPEAK_END = 2400; // waveform plays until here
const MORPH = 1000; // bars travel to their place on the app screen
const STAGGER = 60; // each bar starts a little after the one before
const PHONE_START = 2500;
const PHONE_END = 3400;
const LINE_2_START = 3300;
const TICK_START = 3700;
const FADE_START = 7200;
const FADE_END = 7700;
const LOOP = 8000;
const FINAL = 5000; // the still frame shown when motion is reduced

const C = {
  accent: "#50eaf2",
  fg: "#f1effa",
  muted: "#b4b1d6",
  dim: "#9e9bc4",
  wall: "#6e3a84",
  card: "#2a0835",
};

// Taller bars in the middle, like a voice.
const ENVELOPE = [0.45, 0.7, 0.9, 1, 0.9, 0.7, 0.45];

// Where each bar ends up: the blocks of a simple app screen.
const BLOCKS = [
  { x: 76, y: 44, w: 88, h: 14, rx: 5, color: C.fg }, // header
  { x: 76, y: 68, w: 88, h: 54, rx: 8, color: C.wall }, // image
  { x: 76, y: 134, w: 72, h: 8, rx: 4, color: C.muted }, // text
  { x: 76, y: 148, w: 56, h: 8, rx: 4, color: C.muted },
  { x: 76, y: 162, w: 64, h: 8, rx: 4, color: C.muted },
  { x: 76, y: 184, w: 88, h: 24, rx: 12, color: C.accent }, // button
  { x: 100, y: 220, w: 40, h: 8, rx: 4, color: C.dim }, // footer
];

const clamp01 = (v) => Math.min(1, Math.max(0, v));
const progress = (t, start, end) => clamp01((t - start) / (end - start));
const lerp = (a, b, p) => a + (b - a) * p;
const easeInOut = (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
const easeOut = (p) => 1 - Math.pow(1 - p, 3);
const easeOutBack = (p) => 1 + 2.7 * Math.pow(p - 1, 3) + 1.7 * Math.pow(p - 1, 2);

function lerpColor(a, b, p) {
  const ca = a.match(/\w\w/g).map((h) => parseInt(h, 16));
  const cb = b.match(/\w\w/g).map((h) => parseInt(h, 16));
  return `rgb(${ca.map((v, i) => Math.round(lerp(v, cb[i], p))).join(",")})`;
}

// A bar of the waveform at time t.
function waveBar(i, t) {
  const height = 14 + 46 * ENVELOPE[i] * (0.5 + 0.5 * Math.sin(t / 170 + i * 0.9));
  return { x: 68 + i * 16, y: 140 - height / 2, w: 8, h: height, rx: 4, color: C.accent };
}

function bar(i, t) {
  const p = easeInOut(progress(t, SPEAK_END + i * STAGGER, SPEAK_END + i * STAGGER + MORPH));
  const from = waveBar(i, Math.min(t, SPEAK_END));
  const to = BLOCKS[i];
  if (p === 0) return from;
  return {
    x: lerp(from.x, to.x, p),
    y: lerp(from.y, to.y, p),
    w: lerp(from.w, to.w, p),
    h: lerp(from.h, to.h, p),
    rx: lerp(from.rx, to.rx, p),
    color: lerpColor(from.color, to.color, p),
  };
}

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return reduced;
}

// Milliseconds into the current loop, updated every frame.
function useLoopTime(paused) {
  const [t, setT] = useState(paused ? FINAL : 0);
  useEffect(() => {
    if (paused) {
      setT(FINAL);
      return;
    }
    let frame;
    let start;
    const tick = (now) => {
      start ??= now;
      setT((now - start) % LOOP);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [paused]);
  return t;
}

function SpeakToApp({ t }) {
  const fade = 1 - progress(t, FADE_START, FADE_END);
  const micOpacity = 1 - progress(t, SPEAK_END, SPEAK_END + 300);
  const phone = easeInOut(progress(t, PHONE_START, PHONE_END));
  const badge = easeOutBack(progress(t, TICK_START, TICK_START + 450));
  const check = easeOut(progress(t, TICK_START + 250, TICK_START + 650));

  return (
    <svg
      role="img"
      aria-label="आवाज़ की लहरें ऐप की स्क्रीन बन जाती हैं"
      viewBox="0 0 240 280"
      className="w-[min(300px,72vw)]"
      style={{ maxWidth: "100%", height: "auto" }}
    >
      <g opacity={fade}>
        {/* Microphone, while the user speaks */}
        <g opacity={micOpacity} fill="none" stroke={C.fg} strokeWidth="3" strokeLinecap="round">
          <rect x="112" y="54" width="16" height="26" rx="8" />
          <path d="M103 72 a17 17 0 0 0 34 0" />
          <line x1="120" y1="89" x2="120" y2="96" />
        </g>

        {/* The phone draws itself around the screen */}
        <rect x="60" y="20" width="120" height="240" rx="20" fill="none" stroke={C.muted} strokeWidth="3"
          pathLength="1" strokeDasharray="1" strokeDashoffset={1 - phone} />
        <line x1="108" y1="31" x2="132" y2="31" stroke={C.muted} strokeWidth="3" strokeLinecap="round"
          opacity={phone} />

        {/* Waveform bars that become the app's blocks */}
        {BLOCKS.map((_, i) => {
          const b = bar(i, t);
          return <rect key={i} x={b.x} y={b.y} width={b.w} height={b.h} rx={b.rx} fill={b.color} />;
        })}

        {/* The Vyskar tick: the app is ready */}
        <g transform={`translate(176 34) scale(${badge}) translate(-176 -34)`} opacity={badge > 0 ? 1 : 0}>
          <circle cx="176" cy="34" r="17" fill={C.card} stroke={C.accent} strokeWidth="2.5" />
          <polyline points="168,34 174,41 185,26" fill="none" stroke={C.accent} strokeWidth="4"
            strokeLinecap="round" strokeLinejoin="round" pathLength="1" strokeDasharray="1"
            strokeDashoffset={1 - check} />
        </g>
      </g>
    </svg>
  );
}

function Line({ children, visible }) {
  return (
    <span
      aria-hidden="true"
      className="block"
      style={{ opacity: visible, transform: `translateY(${(1 - visible) * 14}px)` }}
    >
      {children}
    </span>
  );
}

export default function HindiPage() {
  const reduced = usePrefersReducedMotion();
  const t = useLoopTime(reduced);
  const fade = 1 - progress(t, FADE_START, FADE_END);
  const line1 = easeOut(progress(t, 200, 700)) * fade;
  const line2 = easeOut(progress(t, LINE_2_START, LINE_2_START + 500)) * fade;

  return (
    <main
      className="flex min-h-svh flex-col items-center justify-center gap-8 px-6 py-12 text-center"
      style={{
        background: `radial-gradient(circle at 50% 36%, color-mix(in oklch, ${C.accent} 12%, transparent), transparent 55%), var(--color-ink)`,
      }}
    >
      <SpeakToApp t={t} />
      <h1
        aria-label={`${LINE_1} ${LINE_2}`}
        className="text-[clamp(40px,9vw,96px)] leading-[1.25] font-extrabold text-fg"
        style={{ fontFamily: '"Baloo 2", var(--font-sans)' }}
      >
        <Line visible={line1}>{LINE_1}</Line>
        <Line visible={line2}>{LINE_2}</Line>
      </h1>
    </main>
  );
}
