function Primitive({ value }) {
  if (typeof value === "string") {
    return <span className="text-green-700 whitespace-pre-wrap">"{value}"</span>;
  }
  if (typeof value === "number") {
    return <span className="text-blue-700">{value}</span>;
  }
  return <span className="text-purple-700">{String(value)}</span>; // true, false, null
}

function JsonNode({ name, value, depth }) {
  const label = name !== undefined && (
    <>
      <span className="text-sky-800">{typeof name === "number" ? name : `"${name}"`}</span>:{" "}
    </>
  );

  if (value === null || typeof value !== "object") {
    return (
      <div className="pl-4">
        {label}
        <Primitive value={value} />
      </div>
    );
  }

  const isArray = Array.isArray(value);
  const entries = isArray ? value.map((v, i) => [i, v]) : Object.entries(value);
  const [open, close] = isArray ? ["[", "]"] : ["{", "}"];

  return (
    <details open={depth === 0} className="pl-4">
      <summary className="cursor-pointer select-none hover:bg-gray-100">
        {label}
        {open}
        <span className="text-gray-400">
          {" "}
          {entries.length} {isArray ? "items" : "keys"}
        </span>
      </summary>
      {entries.map(([k, v]) => (
        <JsonNode key={k} name={k} value={v} depth={depth + 1} />
      ))}
      <div className="pl-4">{close}</div>
    </details>
  );
}

export default function JsonTree({ value }) {
  return (
    <div className="font-mono text-sm overflow-x-auto rounded border bg-gray-50 p-3">
      <JsonNode value={value} depth={0} />
    </div>
  );
}