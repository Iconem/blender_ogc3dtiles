// remarkMdxMermaid (source.config.ts) turns ```mermaid fences into
// <Mermaid chart="..."/>. Rendered at build time with beautiful-mermaid
// (no DOM, no Mermaid runtime in the browser): the SVG sits in the static
// HTML, so no bundle on diagram pages and no flash before the diagram shows.
// Two SVGs are rendered, one per colour scheme, and CSS shows the one that
// matches the theme (the library takes hex colours, not CSS variables: it
// derives the secondary colours from bg and fg). The values are the docs'
// own light and dark tokens. Covered diagram types: flowchart, class,
// sequence, state, entity relationship, gantt; the docs use the first two.
// A diagram the library cannot parse falls back to its source in a code block.
// The SVG's stylesheet reads --muted, --border, --line and --surface with
// colour-mix fallbacks; the docs' own tokens define --muted and --border as
// background colours, which made the edge labels and class members vanish in
// both themes. The wrapper sets those four to `initial` so the fallbacks apply.
import type React from 'react';
import { renderMermaidSVG } from 'beautiful-mermaid';

const LIGHT = { bg: '#ffffff', fg: '#0a0a0a', accent: '#1a237e', font: 'Geist, Inter, system-ui, sans-serif', transparent: true } as const;
const DARK = { bg: '#0a0a0a', fg: '#fafafa', accent: '#8c9eff', font: 'Geist, Inter, system-ui, sans-serif', transparent: true } as const;

const RESET = { '--muted': 'initial', '--border': 'initial', '--line': 'initial', '--surface': 'initial' } as React.CSSProperties;

function render(chart: string, colors: typeof LIGHT | typeof DARK): string | null {
  try {
    return renderMermaidSVG(chart, { ...colors, padding: 16 });
  } catch {
    return null;
  }
}

export function Mermaid({ chart }: { chart: string }) {
  const light = render(chart, LIGHT);
  const dark = render(chart, DARK);
  if (!light || !dark) {
    return (
      <pre className="overflow-x-auto rounded-lg border bg-fd-muted p-4 text-sm">
        <code>{chart}</code>
      </pre>
    );
  }
  // Fitted to the text column by default; a click (a checkbox, so no script) shows it at full size, scrollable.
  return (
    <label className="my-6 block cursor-zoom-in has-[:checked]:cursor-zoom-out" style={RESET} title="Click to zoom">
      <input type="checkbox" className="peer sr-only" aria-label="Show the diagram at full size" />
      <div className="overflow-x-auto [&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full peer-checked:[&_svg]:max-w-none">
        <div className="dark:hidden" dangerouslySetInnerHTML={{ __html: light }} />
        <div className="hidden dark:block" dangerouslySetInnerHTML={{ __html: dark }} />
      </div>
      <span className="mt-1 block text-center text-xs text-fd-muted-foreground peer-checked:hidden">Click the diagram to zoom</span>
    </label>
  );
}
