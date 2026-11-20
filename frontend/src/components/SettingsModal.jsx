import { useEffect, useRef } from 'react'

// A native <dialog>: the browser handles focus, Escape to close and the backdrop.
export default function Modal({ open, onClose, labelledBy, children }) {
  const ref = useRef(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      aria-labelledby={labelledBy}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose()
      }}
      className="m-auto w-[min(520px,calc(100%-32px))] bg-transparent p-0 text-fg backdrop:bg-black/60 backdrop:backdrop-blur-sm"
    >
      {open && (
        <>
          {/* Escape and the backdrop also close it, but touch screen readers need a button. */}
          <div className="flex justify-end">
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="mb-2 grid h-11 w-11 place-items-center rounded-full border border-wall bg-card text-muted hover:text-fg"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true" className="h-5 w-5">
                <path d="M6 6l12 12M18 6L6 18" />
              </svg>
            </button>
          </div>
          {children}
        </>
      )}
    </dialog>
  )
}