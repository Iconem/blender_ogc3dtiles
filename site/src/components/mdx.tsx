import defaultMdxComponents from 'fumadocs-ui/mdx';
import { ImageZoom } from 'fumadocs-ui/components/image-zoom';
import type { MDXComponents } from 'mdx/types';
import { Mermaid } from '@/components/mermaid';
import { basePath } from '@/lib/shared';

const withBase = (src: unknown) =>
  typeof src === 'string' && src.startsWith('/') && !src.startsWith(`${basePath}/`) ? `${basePath}${src}` : (src as string | undefined);

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
    // the clips of the Videos page (/video/..., copied into public/ like the screenshots): same basePath fix as img
    video: ({ src, poster, ...props }: React.ComponentProps<'video'>) => (
      <video {...props} src={withBase(src)} poster={withBase(poster)} />
    ),
    Mermaid,
    ...components,
  } satisfies MDXComponents;
}

export const useMDXComponents = getMDXComponents;
