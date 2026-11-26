// Why a build stopped, in words for the person who asked for the app.
//
// Some failure reasons come straight from Vyskar's own checks, such as
// "Requirements failed: requirement R1: source_quote 'bill amount' does not
// appear in the request". They help when tracing a build, but read as noise
// to someone who only described an app. For those, a plain sentence with a
// next step goes first and the original reason is kept as the detail.
// Reasons already written for people (a rejected request, a key problem, an
// app that could not be found) are shown as they are.

const SMALLER = 'Try again, or start with a smaller first version and add to it later.'

const PLAIN = [
  [
    /^Requirements failed: /,
    "Vyskar couldn't work out exactly what the app should do from this description. Try describing what someone does in the app, one step at a time.",
  ],
  [/^Architecture failed: /, `Vyskar couldn't plan how to put this app together. ${SMALLER}`],
  [/^Test planning failed: /, `Vyskar couldn't plan the tests that check this app works. ${SMALLER}`],
  [/^A database migration failed: /, "Setting up the app's database didn't work. Try building it again in a few minutes."],
  [/^(build failed|stopped early)$/, `Vyskar couldn't get the app to build and pass its tests. ${SMALLER}`],
]

// { text, detail }: what to show, and the original reason when `text` is a
// plain rewording of it (else detail is '').
export function failureText(reason) {
  const raw = (reason || '').replace(/^(key rejected|no credit): /, '')
  for (const [pattern, text] of PLAIN) {
    if (pattern.test(raw)) return { text, detail: raw }
  }
  return { text: raw, detail: '' }
}
