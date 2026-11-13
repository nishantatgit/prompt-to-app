// Color checks for chart palettes: can each pair of series colors be told
// apart, by people with normal color vision and with the three common types
// of color blindness, and does each color stand out from the background?
//
// Distances are measured in OKLab (Björn Ottosson, 2020), scaled by 100.
// Color blindness is simulated with the matrices of Machado, Oliveira and
// Fernandes (2009) at full severity, applied in linear RGB.

export type RGB = [number, number, number] // 0 to 255

// Thresholds. Below MIN_NORMAL, two colors look alike to most people. Below
// MIN_CVD under a simulation, people with that type of color blindness
// struggle to tell them apart. MIN_CONTRAST is WCAG's 3:1 for graphics.
export const MIN_NORMAL = 15
export const MIN_CVD = 8
export const MIN_CONTRAST = 3

const CVD = {
  protanopia: [
    [0.152286, 1.052583, -0.204868],
    [0.114503, 0.786281, 0.099216],
    [-0.003882, -0.048116, 1.051998],
  ],
  deuteranopia: [
    [0.367322, 0.860646, -0.227968],
    [0.280085, 0.672501, 0.047413],
    [-0.01182, 0.04294, 0.968881],
  ],
  tritanopia: [
    [1.255528, -0.076749, -0.178779],
    [-0.078411, 0.930809, 0.147602],
    [0.004733, 0.691367, 0.3039],
  ],
} as const

export type Vision = 'normal' | keyof typeof CVD

export function parseColor(css: string): RGB | null {
  const m = css.match(/rgba?\(\s*([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)/)
  if (m) {
    const alpha = m[4] === undefined ? 1 : parseFloat(m[4]) / (m[4].endsWith('%') ? 100 : 1)
    if (alpha < 0.5) return null // mostly transparent: not a series color
    return [Number(m[1]), Number(m[2]), Number(m[3])]
  }
  const hex = css.trim().match(/^#([\da-f]{3}|[\da-f]{6})$/i)
  if (!hex) return null
  const h = hex[1].length === 3 ? [...hex[1]].map((c) => c + c).join('') : hex[1]
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)) as RGB
}

const toLinear = (c: number) => {
  const v = c / 255
  return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
}

function linear(rgb: RGB): [number, number, number] {
  return [toLinear(rgb[0]), toLinear(rgb[1]), toLinear(rgb[2])]
}

function simulate(lin: [number, number, number], vision: Vision): [number, number, number] {
  if (vision === 'normal') return lin
  const m = CVD[vision]
  const clamp = (v: number) => Math.min(1, Math.max(0, v))
  return m.map((row) => clamp(row[0] * lin[0] + row[1] * lin[1] + row[2] * lin[2])) as [
    number,
    number,
    number,
  ]
}

function oklab([r, g, b]: [number, number, number]): [number, number, number] {
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ]
}

// How different two colors look, for one kind of vision (OKLab distance x 100).
export function distance(a: RGB, b: RGB, vision: Vision = 'normal'): number {
  const [x, y] = [oklab(simulate(linear(a), vision)), oklab(simulate(linear(b), vision))]
  return 100 * Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2])
}

// WCAG contrast ratio, from 1 to 21.
export function contrast(a: RGB, b: RGB): number {
  const lum = (c: RGB) => {
    const [r, g, bl] = linear(c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl
  }
  const [hi, lo] = [lum(a), lum(b)].sort((p, q) => q - p)
  return (hi + 0.05) / (lo + 0.05)
}

// Grays and near grays are axes, gridlines and text, not series colors.
export function isNeutral(rgb: RGB): boolean {
  const [, a, b] = oklab(linear(rgb))
  return Math.hypot(a, b) < 0.03
}

export type Problem = { a: string; b?: string; check: string; value: number; needed: number }

const hex = (c: RGB) => '#' + c.map((v) => Math.round(v).toString(16).padStart(2, '0')).join('')

// Every problem with a palette on a background; an empty list means it passes.
export function paletteProblems(colors: RGB[], background: RGB): Problem[] {
  const problems: Problem[] = []
  for (const c of colors) {
    const ratio = contrast(c, background)
    if (ratio < MIN_CONTRAST)
      problems.push({ a: hex(c), check: 'contrast with background', value: ratio, needed: MIN_CONTRAST })
  }
  for (let i = 0; i < colors.length; i++) {
    for (let j = i + 1; j < colors.length; j++) {
      for (const vision of ['normal', ...Object.keys(CVD)] as Vision[]) {
        const d = distance(colors[i], colors[j], vision)
        const needed = vision === 'normal' ? MIN_NORMAL : MIN_CVD
        if (d < needed)
          problems.push({ a: hex(colors[i]), b: hex(colors[j]), check: vision, value: d, needed })
      }
    }
  }
  return problems
}
