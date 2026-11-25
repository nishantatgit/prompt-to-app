import { describe, expect, it, vi } from 'vitest'
import { UNCONFIRMED, Unconfirmed, confirmPayment, isTemporary } from './payment.js'

const proof = { razorpay_order_id: 'order_1', razorpay_payment_id: 'pay_1', razorpay_signature: 'sig' }
const noWait = () => Promise.resolve()

function failure(message, extra) {
  return Object.assign(new Error(message), extra)
}

describe('isTemporary', () => {
  it('asks again when Vyskar could not be reached or had a server error', () => {
    expect(isTemporary(failure('away', { unreachable: true }))).toBe(true)
    expect(isTemporary(failure('slow', { status: 502 }))).toBe(true)
  })

  it('takes a refusal as final', () => {
    expect(isTemporary(failure('no match', { status: 400 }))).toBe(false)
    expect(isTemporary(new Error('plain'))).toBe(false)
  })
})

describe('confirmPayment', () => {
  it('returns the reply when the first try works', async () => {
    const verify = vi.fn().mockResolvedValue({ builds_left: 5, payment_id: 'pay_1' })
    await expect(confirmPayment(proof, { verify, wait: noWait })).resolves.toEqual({ builds_left: 5, payment_id: 'pay_1' })
    expect(verify).toHaveBeenCalledTimes(1)
  })

  it('asks again after a dropped connection and returns the later reply', async () => {
    const wait = vi.fn(noWait)
    const verify = vi
      .fn()
      .mockRejectedValueOnce(failure("Can't reach Vyskar", { unreachable: true }))
      .mockResolvedValueOnce({ builds_left: 5, payment_id: 'pay_1' })
    await expect(confirmPayment(proof, { verify, wait })).resolves.toMatchObject({ builds_left: 5 })
    expect(verify).toHaveBeenCalledTimes(2)
    expect(wait).toHaveBeenCalledWith(2000)
  })

  it('points to Restore with the payment ID when every try fails', async () => {
    const verify = vi.fn().mockRejectedValue(failure('Razorpay slow', { status: 502 }))
    const error = await confirmPayment(proof, { verify, wait: noWait }).catch((e) => e)
    expect(error).toBeInstanceOf(Unconfirmed)
    expect(error.message).toBe(UNCONFIRMED)
    expect(error.paymentId).toBe('pay_1')
    expect(verify).toHaveBeenCalledTimes(3)
  })

  it('does not ask again when the payment was refused', async () => {
    const refused = failure('This payment does not match the order.', { status: 400 })
    const verify = vi.fn().mockRejectedValue(refused)
    await expect(confirmPayment(proof, { verify, wait: noWait })).rejects.toBe(refused)
    expect(verify).toHaveBeenCalledTimes(1)
  })
})
