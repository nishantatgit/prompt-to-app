
## Visual design: building

Follow visual_design exactly. These rules cover what it does not say.

Layout
- The app works at phone width (375px) with no sideways scrolling. Keep at
  least 16px of space at the left and right edges. Rows wrap or stack into
  one column on narrow screens, and flex or grid children that hold text get
  min-width: 0 so long words wrap instead of widening the page.
- Images and media are never wider than their container (max-width: 100%).
- Space groups of elements with flex or grid and gap, not margins on each
  element.

Structure
- A border, shadow or filled background marks something as a separate
  object. Use them only where that is true, such as items in a set of
  products. Not every section is a card.
- Number things (1, 2, 3) only when they are a real sequence, such as the
  steps of a process.
- Repeated items share one layout, padding and alignment.

Content
- The app opens in a realistic working state with real looking sample
  content, never lorem ipsum and never an empty shell. When the user should
  replace sample content, say so on the page.
- A landing page opens with a hero. Without a real photo, use a large colored
  gradient as the image placeholder, not an icon.
- Name things by what people recognize. A button says exactly what happens
  ("Send message"), and its confirmation uses the same words ("Message
  sent"). Errors say what went wrong and how to fix it, without apologizing.
  An empty screen says what to do next.

Motion
- One deliberate moment, such as a result appearing, is better than effects
  on every element.

Charts, when the app has them
- Pick the chart by what the data shows: change over time is a line,
  comparing categories is a bar, a single headline number is just the number
  with a label.
- One y axis per chart. Two measures with different scales get two charts.
- Each category keeps its color, also when a filter hides others.
- Two or more series need a legend, so meaning never depends on color alone.
- Success, warning and error colors are only for state, never for a data
  series.
