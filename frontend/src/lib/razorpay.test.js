import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { pay } from './razorpay'

// A stand-in for Razorpay Standard Checkout: the test drives its callbacks.
let checkout

class FakeRazorpay {
  constructor(options) {
    this.options = options
    this.events = {}
    checkout = this
  }
  on(name, fn) {
    this.events[name] = fn
  }
  open() {}
  fail(description) {
    this.events['payment.failed']?.({ error: { description } })
  }
  succeed(proof) {
    this.options.handler(proof)
  }
  close() {
    this.options.modal.ondismiss()
  }
}

const ORDER = { keyId: 'rzp_test', orderId: 'order_1', amount: 9900, description: '10 app builds' }
const PROOF = { razorpay_payment_id: 'pay_1', razorpay_order_id: 'order_1', razorpay_signature: 'sig' }

beforeEach(() => {
  window.Razorpay = FakeRazorpay
})

afterEach(() => {
  delete window.Razorpay
  checkout = null
})

describe('pay', () => {
  it('resolves with the proof when the payment goes through', async () => {
    const paid = pay(ORDER)
    await Promise.resolve()
    checkout.succeed(PROOF)
    await expect(paid).resolves.toEqual(PROOF)
  })

  it('resolves with null when the window is closed without paying', async () => {
    const paid = pay(ORDER)
    await Promise.resolve()
    checkout.close()
    await expect(paid).resolves.toBeNull()
  })

  it('still resolves with the proof when a retry succeeds after a failed attempt', async () => {
    const paid = pay(ORDER)
    await Promise.resolve()
    checkout.fail('Your bank declined the payment.')
    checkout.succeed(PROOF)
    await expect(paid).resolves.toEqual(PROOF)
  })

  it('says why it failed when the window is closed after a failed attempt', async () => {
    const paid = pay(ORDER)
    await Promise.resolve()
    checkout.fail('Your bank declined the payment.')
    checkout.close()
    await expect(paid).rejects.toThrow('Your bank declined the payment.')
  })

  it('has a fallback message when Razorpay gives no reason', async () => {
    const paid = pay(ORDER)
    await Promise.resolve()
    checkout.events['payment.failed']({})
    checkout.close()
    await expect(paid).rejects.toThrow('The payment did not go through.')
  })
})
