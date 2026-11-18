// While Vyskar builds, a small app assembles itself in step with the real
// stages: the frame draws, the plan writes, the layout appears, the parts
// fill in, each gets a tick when tested, and the app glows when it goes live.
// stage: index in JobView's STAGES, -1 before the first one.

const CAPTIONS = [
  'Reading your idea',
  'Writing down what it must do',
  'Sketching the screens',
  'Setting up the project',
  'Building it',
  'Planning how to test it',
  'Testing it like a real user would',
  'Putting it online',
]

const CARDS = [
  { x: 28, y: 132, w: 164, h: 44 },
  { x: 28, y: 186, w: 164, h: 44 },
]

export default function BuildAnimation({ stage }) {
  const at = (n) => (stage >= n ? 'on' : '')
  const caption = CAPTIONS[Math.max(0, stage)]

  return (
    <figure className="build-anim mt-5 flex flex-col items-center gap-3" aria-hidden="true" data-stage={stage}>
      <svg viewBox="0 0 220 300" className="h-56 w-auto overflow-visible">
        <defs>
          <linearGradient id="ba-shine" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0" stopColor="white" stopOpacity="0" />
            <stop offset="0.5" stopColor="white" stopOpacity="0.35" />
            <stop offset="1" stopColor="white" stopOpacity="0" />
          </linearGradient>
          <clipPath id="ba-screen">
            <rect x="12" y="12" width="196" height="276" rx="22" />
          </clipPath>
        </defs>

        {/* 7: live glow behind the phone */}
        <rect className={`ba-glow ${at(7)}`} x="4" y="4" width="212" height="292" rx="30" />

        {/* 0: the phone frame draws itself */}
        <rect className={`ba-frame ${at(0)}`} x="12" y="12" width="196" height="276" rx="22" pathLength="1" />

        <g clipPath="url(#ba-screen)">
          {/* 3: header bar slides in */}
          <g className={`ba-header ${at(3)}`}>
            <rect x="12" y="12" width="196" height="44" className="ba-fill-soft" />
            <circle cx="36" cy="34" r="7" className="ba-fill-accent" />
            <rect x="50" y="30" width="56" height="8" rx="4" className="ba-fill-fg" />
          </g>

          {/* 1: the plan writes itself as lines of text */}
          {[0, 1, 2].map((i) => (
            <rect
              key={i}
              className={`ba-line ${at(1)}`}
              style={{ transitionDelay: `${i * 220}ms` }}
              x="28"
              y={72 + i * 16}
              width={[150, 118, 136][i]}
              height="7"
              rx="3.5"
            />
          ))}

          {/* 2: layout boxes, 4: filled in, 6: ticked */}
          {CARDS.map((c, i) => (
            <g key={i}>
              <rect className={`ba-box ${at(2)}`} style={{ transitionDelay: `${i * 180}ms` }} x={c.x} y={c.y} width={c.w} height={c.h} rx="10" />
              <rect className={`ba-solid ${at(4)}`} style={{ transitionDelay: `${i * 260}ms` }} x={c.x} y={c.y} width={c.w} height={c.h} rx="10" />
              <rect className={`ba-text ${at(4)}`} style={{ transitionDelay: `${300 + i * 260}ms` }} x={c.x + 14} y={c.y + 13} width={70 + i * 20} height="7" rx="3.5" />
              <rect className={`ba-text ${at(4)}`} style={{ transitionDelay: `${380 + i * 260}ms` }} x={c.x + 14} y={c.y + 26} width={46} height="6" rx="3" />
              <g className={`ba-tick ${at(6)}`} style={{ transitionDelay: `${i * 350}ms` }} transform={`translate(${c.x + c.w - 22} ${c.y + c.h / 2})`}>
                <circle r="10" className="ba-fill-accent" />
                <polyline points="-4,0 -1,3.5 4.5,-3" className="ba-tick-mark" />
              </g>
            </g>
          ))}

          {/* button: outlined at 2, filled at 4 */}
          <rect className={`ba-box ${at(2)}`} style={{ transitionDelay: '360ms' }} x="28" y="244" width="164" height="30" rx="15" />
          <rect className={`ba-button ${at(4)}`} style={{ transitionDelay: '600ms' }} x="28" y="244" width="164" height="30" rx="15" />

          {/* 4 to 6: a shine sweeps across while it is being built */}
          {stage >= 4 && stage < 7 && <rect className="ba-shine" x="-120" y="12" width="110" height="276" fill="url(#ba-shine)" />}
        </g>

        {/* 7: live */}
        <g className={`ba-live ${at(7)}`} transform="translate(110 14)">
          <rect x="-26" y="-11" width="52" height="22" rx="11" className="ba-fill-accent" />
          <circle cx="-13" cy="0" r="3.5" className="ba-live-dot" />
          <text x="5" y="4" textAnchor="middle" className="ba-live-text">live</text>
        </g>
      </svg>
      <figcaption key={caption} className="ba-caption text-sm text-muted">
        {caption}
        <span className="ba-dots"><i>.</i><i>.</i><i>.</i></span>
      </figcaption>
    </figure>
  )
}
