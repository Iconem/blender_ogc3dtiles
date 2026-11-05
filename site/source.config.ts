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
  },
});
