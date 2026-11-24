// A count with its noun, so the last build reads "1 build", not "1 builds".
// builds(3, 'free') is "3 free builds".
export function builds(count, adjective = '') {
  const noun = count === 1 ? 'build' : 'builds'
  return [count, adjective, noun].filter((part) => part !== '').join(' ')
}
