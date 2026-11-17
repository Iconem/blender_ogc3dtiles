import defaultMdxComponents from 'fumadocs-ui/mdx';
import { ImageZoom } from 'fumadocs-ui/components/image-zoom';
import type { MDXComponents } from 'mdx/types';
import { Mermaid } from '@/components/mermaid';
import { basePath } from '@/lib/shared';

export function getMDXComponents(components?: MDXComponents) {
  return {
    ...defaultMdxComponents,
    // every screenshot opens full size on click. Images are authored as /img/... and left as such by the remark-image
    // plugin (useImport: false in source.config.ts): the basePath goes in here, since next/image leaves a plain string
    // src alone.
    img: ({ src, ...props }) => (
      <ImageZoom
        {...(props as React.ComponentProps<typeof ImageZoom>)}
        src={typeof src === 'string' && src.startsWith('/') && !src.startsWith(`${basePath}/`) ? `${basePath}${src}` : (src as string)}
      />
    ),
    Mermaid,
    ...components,
  } satisfies MDXComponents;
}

export const useMDXComponents = getMDXComponents;
