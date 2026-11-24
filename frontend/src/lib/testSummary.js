// A build's test summary comes from the server as lines of text: first a
// count ("7/8 tests passed."), then one line per failed test or run error.
// The count goes next to the confidence; the rest is listed under it.
export function splitTestSummary(summary) {
  const lines = String(summary || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
  return {
    headline: (lines[0] || '').replace(/\.$/, ''),
    details: lines.slice(1),
  }
}
