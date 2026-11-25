// Confirming a Razorpay payment with Vyskar, after the money is taken.
//
// By the time the browser has Razorpay's proof, the person has paid. If the
// confirm call then fails for a moment (no signal after switching back from
// a UPI app, or Vyskar restarting), the builds must not be lost: it is asked
// again a few times, and if it still fails the person is pointed to Restore
// with their payment ID, which asks Razorpay directly.

import { verifyPayment } from './api.js'

export const UNCONFIRMED =
  "Your payment went through, but Vyskar couldn't add the builds yet. " +
  'Tap Restore below in a minute to add them.'

// Waits between tries, in milliseconds.
const WAITS = [2000, 5000]

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

// A failure worth asking again about: Vyskar or Razorpay could not be
// reached, or answered with a server error. A refusal (400) is final.
export function isTemporary(error) {
  return Boolean(error?.unreachable) || (typeof error?.status === 'number' && error.status >= 500)
}

export class Unconfirmed extends Error {
  constructor(paymentId) {
    super(UNCONFIRMED)
    this.paymentId = paymentId
  }
}

// The confirm reply ({ builds_left, payment_id }). Throws Unconfirmed when
// the payment could not be confirmed for now, and the API's error when the
// payment was refused.
export async function confirmPayment(proof, { verify = verifyPayment, wait = sleep, waits = WAITS } = {}) {
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await verify(proof)
    } catch (error) {
      if (!isTemporary(error)) throw error
      if (attempt >= waits.length) throw new Unconfirmed(proof?.razorpay_payment_id || '')
      await wait(waits[attempt])
    }
  }
}
