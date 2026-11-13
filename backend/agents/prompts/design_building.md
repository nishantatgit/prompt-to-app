
## Visual design: building in Vyskar

The Frontend Design guide above is how to design. In Vyskar the design plan
is already made: follow visual_design exactly, and skip the guide's planning
and review pass. These notes adapt the guide to that setup and add Vyskar's
own rules.

- You cannot ask the client anything or take screenshots. Check your work by
  reading your code against the plan and these rules.

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
- Repeated items share one layout, padding and alignment.

Content
- The app opens in a realistic working state with real looking sample
  content, never lorem ipsum and never an empty shell. When the user should
  replace sample content, say so on the page.
- A landing page opens with a hero. Without a real photo, use a large colored
  gradient as the image placeholder, not an icon.

Light and dark
- The app follows the device's light or dark setting. Define every color as a
  token in src/index.css, then give the dark values in the same file:
  @media (prefers-color-scheme: dark) { :root { --color-surface: ...; } }
  redefines only the tokens. Components use the tokens and never set a color
  of their own, so they change with the theme.
- Set the page background and text color on body from the tokens.
- Check text contrast in both themes: at least 4.5:1 for text, 3:1 for icons,
  borders of inputs and chart marks.
- Native controls follow the theme with color-scheme: light dark on :root.

Charts, when the app has them
- Pick the chart by what the data shows: change over time is a line,
  comparing categories is a bar, a single headline number is just the number
  with a label.
- One y axis per chart. Two measures with different scales get two charts.
- Each category keeps its color, also when a filter hides others.
- Two or more series need a legend, so meaning never depends on color alone.
- Success, warning and error colors are only for state, never for a data
  series.
