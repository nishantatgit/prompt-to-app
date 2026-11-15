import { useState } from 'react'
import { createOrder, verifyPayment } from '../lib/api.js'
import { pay } from '../lib/razorpay.js'

const rupees = (n) => `₹${n.toLocaleString('en-IN')}`

// Packs of builds that run on Vyskar's AI, no key needed.
export default function BuyBuilds({ credits, onBought }) {
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState('')

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
        description: `${pack.builds} app builds`,
      })
      if (!proof) return // closed the window
      const { builds_left } = await verifyPayment(proof)
      setDone(`Paid. You have ${builds_left} builds.`)
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
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {credits.packs.map((pack) => (
          <button
            key={pack.id}
            type="button"
            onClick={() => buy(pack)}
            disabled={Boolean(busy)}
            aria-label={`Buy ${pack.builds} builds for ${rupees(pack.price_inr)}`}
            className="flex min-h-11 flex-col items-start gap-1 rounded-xl border border-wall p-4 text-left hover:border-accent disabled:opacity-60"
          >
            <span className="font-display text-xl font-bold">{pack.builds} builds</span>
            <span className="text-accent">{rupees(pack.price_inr)}</span>
            <span className="text-xs text-dim">
              {busy === pack.id ? 'Opening payment...' : `${rupees(Math.round(pack.price_inr / pack.builds))} per build`}
            </span>
          </button>
        ))}
      </div>
      <p className="mt-3 text-xs text-dim">UPI, cards and netbanking, through Razorpay. Builds are saved in this browser.</p>
      {done && <p className="mt-3 text-sm text-accent">{done}</p>}
      {error && <p className="mt-3 text-sm text-accent">{error}</p>}
    </section>
  )
}
