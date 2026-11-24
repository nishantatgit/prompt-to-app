import { useState } from 'react'
import { createOrder, restoreBuilds, verifyPayment } from '../lib/api.js'
import { pay } from '../lib/razorpay.js'
import { builds } from '../lib/plural.js'

const rupees = (n) => `₹${n.toLocaleString('en-IN')}`

// Packs of builds that run on Vyskar's AI, no key needed.
export default function BuyBuilds({ credits, onBought }) {
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState('')
  const [paymentId, setPaymentId] = useState('')
  const [restoring, setRestoring] = useState(false)
  const [restoreId, setRestoreId] = useState('')

  async function restore(e) {
    e.preventDefault()
    setError('')
    setDone('')
    try {
      const { builds_left } = await restoreBuilds(restoreId.trim())
      setDone(`Restored. You have ${builds(builds_left)}.`)
      setRestoring(false)
      onBought(builds_left)
    } catch (err) {
      setError(err.message)
    }
  }

  async function buy(pack) {
    setBusy(pack.id)
    setError('')
    setDone('')
    try {
      const order = await createOrder(pack.id)
      const proof = await pay({
        keyId: order.key_id,
        orderId: order.order_id,
        amount: order.amount,
        description: builds(pack.builds, 'app'),
      })
      if (!proof) return // closed the window
      const { builds_left, payment_id } = await verifyPayment(proof)
      setDone(`Paid. You have ${builds(builds_left)}.`)
      setPaymentId(payment_id || proof.razorpay_payment_id)
      onBought(builds_left)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  return (
    <section aria-labelledby="buy-title" className="rounded-2xl border border-line bg-card p-6">
      <h2 id="buy-title" className="font-display text-lg font-bold">Buy builds</h2>
      <p className="mt-2 text-sm leading-relaxed text-muted">
        No AI key needed. Each build or change of an app uses one.
        {credits.builds_left > 0 && ` You have ${credits.builds_left} left.`}
      </p>
      {credits.packs.length === 0 && (
        <p className="mt-5 text-sm text-muted">No packs are on sale right now. Check back soon.</p>
      )}
      <div className="mt-5 grid gap-3 sm:grid-cols-2 empty:hidden">
        {credits.packs.map((pack) => (
          <button
            key={pack.id}
            type="button"
            onClick={() => buy(pack)}
            disabled={Boolean(busy)}
            className="flex min-h-11 flex-col items-start gap-1 rounded-xl border border-wall p-4 text-left hover:border-accent disabled:opacity-60"
          >
            <span className="font-display text-xl font-bold">
              <span className="sr-only">Buy </span>
              {builds(pack.builds)}
            </span>
            <span className="text-accent">{rupees(pack.price_inr)}</span>
            <span className="text-xs text-dim">
              {busy === pack.id ? 'Opening payment...' : `${rupees(Math.round(pack.price_inr / pack.builds))} per build`}
            </span>
          </button>
        ))}
      </div>
      <p className="mt-3 text-xs text-dim">UPI, cards and netbanking, through Razorpay.</p>
      {done && <p className="mt-3 text-sm text-accent">{done}</p>}
      {paymentId && (
        <p className="mt-2 text-sm text-muted">
          Keep your payment ID <span className="select-all font-mono text-fg">{paymentId}</span>. It
          brings these builds to another phone or browser. It's also in your Razorpay receipt.
        </p>
      )}
      {restoring ? (
        <form onSubmit={restore} className="mt-4 flex flex-col gap-2 sm:flex-row">
          <label htmlFor="restore-id" className="sr-only">Payment ID</label>
          <input
            id="restore-id"
            required
            value={restoreId}
            onChange={(e) => setRestoreId(e.target.value)}
            placeholder="pay_..."
            autoComplete="off"
            spellCheck={false}
            className="min-h-11 flex-1 rounded-xl border border-wall bg-ink px-3 font-mono text-base text-fg placeholder:text-dim"
          />
          <button type="submit" className="min-h-11 rounded-full border border-wall px-5 text-sm text-fg">
            Restore
          </button>
        </form>
      ) : (
        <button
          type="button"
          onClick={() => setRestoring(true)}
          className="mt-3 min-h-11 text-sm text-muted underline underline-offset-4"
        >
          Bought builds before? Restore them with your payment ID
        </button>
      )}
      {error && <p role="alert" className="mt-3 text-sm text-danger">{error}</p>}
    </section>
  )
}
