// Razorpay Standard Checkout, loaded only when someone buys.
const SCRIPT = 'https://checkout.razorpay.com/v1/checkout.js'
let loading

function loadCheckout() {
  if (window.Razorpay) return Promise.resolve()
  loading =
    loading ||
    new Promise((resolve, reject) => {
      const script = document.createElement('script')
      script.src = SCRIPT
      script.onload = resolve
      script.onerror = () => {
        loading = null
        reject(new Error("Couldn't open the payment window. Check your connection."))
      }
      document.head.appendChild(script)
    })
  return loading
}

// Resolves with Razorpay's proof of payment, or null if the window was closed.
// A failed attempt does not end it: Razorpay keeps the window open so the
// visitor can try again, and a later attempt can still succeed. The failure
// only counts if they close the window without paying.
export async function pay({ keyId, orderId, amount, description }) {
  await loadCheckout()
  return new Promise((resolve, reject) => {
    let failure = null
    const checkout = new window.Razorpay({
      key: keyId,
      order_id: orderId,
      amount,
      currency: 'INR',
      name: 'Vyskar',
      description,
      theme: { color: '#4A0E5C' },
      handler: (proof) => resolve(proof),
      modal: { ondismiss: () => (failure ? reject(new Error(failure)) : resolve(null)) },
    })
    checkout.on('payment.failed', (event) => {
      failure = event?.error?.description || 'The payment did not go through.'
    })
    checkout.open()
  })
}
