import { useState } from 'react'

export function calculatePerPerson(bill, tipPercent, people) {
  if (!(people >= 1)) return 0
  return (bill * (1 + tipPercent / 100)) / people
}

function Field({ id, label, value, onChange }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <input
        id={id}
        type="number"
        inputMode="decimal"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border px-3 py-2"
      />
    </div>
  )
}

export default function App() {
  const [bill, setBill] = useState('')
  const [tip, setTip] = useState('')
  const [people, setPeople] = useState('1')

  const perPerson = calculatePerPerson(Number(bill), Number(tip), Number(people))

  return (
    <main className="mx-auto flex max-w-md flex-col gap-4 p-6">
      <h1 className="text-2xl font-semibold">Tip calculator</h1>
      <Field id="bill" label="Bill amount" value={bill} onChange={setBill} />
      <Field id="tip" label="Tip percent" value={tip} onChange={setTip} />
      <Field id="people" label="Number of people" value={people} onChange={setPeople} />
      <p className="text-lg">
        Each person pays{' '}
        <output aria-label="Per person" className="font-semibold">
          {perPerson.toFixed(2)}
        </output>
      </p>
    </main>
  )
}
