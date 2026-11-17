import { defineConfig } from 'fumadocs-mdx/config';
import { remarkMdxMermaid } from 'fumadocs-core/mdx-plugins';
import rehypeRaw from 'rehype-raw';

// The pages are .md files (CommonMark, not MDX): URL templates such as {z}/{x}/{y} stay literal. rehype-raw keeps the
// little raw HTML they use; the MDX node types fumadocs injects (frontmatter exports, the <Mermaid> element made from
// ```mermaid fences) must pass through it untouched.
const MDX_NODE_TYPES = ['mdxFlowExpression', 'mdxJsxFlowElement', 'mdxJsxTextElement', 'mdxTextExpression', 'mdxjsEsm'];

export default defineConfig({
  mdxOptions: {
    remarkPlugins: [remarkMdxMermaid],
    rehypePlugins: (defaults) => [[rehypeRaw, { passThrough: MDX_NODE_TYPES }], ...defaults],
    // Images stay at their public path (/img/..., copied into public/ by scripts/sync-content.mjs). The default
    // (useImport) turns each one into an import, so Next bundles a hashed second copy into _next/static/media. The
    // plugin still reads width and height from the file in public/; components/mdx.tsx adds the basePath, which
    // next/image does not do for a plain string src. The slide decks show the same files by URL.
    remarkImageOptions: { useImport: false },
  },
});
