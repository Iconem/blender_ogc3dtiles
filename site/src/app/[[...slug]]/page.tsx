import { notFound } from 'next/navigation';
import type { Metadata } from 'next';
import { DocsBody, DocsDescription, DocsPage, DocsTitle } from 'fumadocs-ui/layouts/docs/page';
import { createRelativeLink } from 'fumadocs-ui/mdx';
import { source } from '@/lib/source';
import { getMDXComponents } from '@/components/mdx';
import { canonicalHost, basePath, ownHost } from '@/lib/shared';

// An OPTIONAL catch-all: content/docs/index.md (the repo root README) is the site's landing page, so "/" is a docs page
// like any other rather than a separate marketing route.
export default async function Page(props: { params: Promise<{ slug?: string[] }> }) {
  const { slug } = await props.params;
  const page = source.getPage(slug);
  if (!page) notFound();

  const MDX = page.data.body;
  const RelativeLink = createRelativeLink(source, page);

  return (
    <DocsPage toc={page.data.toc} full={page.data.full}>
      <DocsTitle>{page.data.title}</DocsTitle>
      <DocsDescription>{page.data.description}</DocsDescription>
      <DocsBody>
        <MDX
          components={getMDXComponents({
            // a link to the latest release is the page's download button
            a: (props) =>
              typeof props.href === 'string' && props.href.endsWith('/releases/latest') ? (
                <a
                  href={props.href}
                  className="not-prose inline-flex items-center gap-2 rounded-lg bg-fd-primary px-4 py-2 text-sm font-medium text-fd-primary-foreground no-underline transition-colors hover:bg-fd-primary/85"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M12 3v12" />
                    <path d="m7 10 5 5 5-5" />
                    <path d="M5 21h14" />
                  </svg>
                  {props.children}
                </a>
              ) : (
                <RelativeLink {...props} href={ownHost(props.href)} />
              ),
          })}
        />
      </DocsBody>
    </DocsPage>
  );
}

const homeTitle = '3D Tiles for Blender: free add-on to stream Google Photorealistic 3D Tiles, Cesium ion, point clouds and Gaussian splats';
const homeDescription =
  'A free, open-source Blender add-on (extension) that streams OGC 3D Tiles into the viewport and renders: Google Photorealistic 3D Tiles, Cesium ion, tiled meshes, point clouds, Gaussian splats, terrain and raster overlays, with cesium-native.';

export async function generateStaticParams() {
  return source.generateParams();
}

export async function generateMetadata(props: { params: Promise<{ slug?: string[] }> }): Promise<Metadata> {
  const { slug } = await props.params;
  const page = source.getPage(slug);
  if (!page) notFound();

  // The landing page IS the site, so it takes the bare name rather than the "%s — Open Geodata Catalog" template
  // (which would otherwise render "Open Geodata Catalog — Open Geodata Catalog").
  // Home: the words people search for, which the short page heading does not hold.
  const home = page.url === '/';
  const title = home ? { absolute: homeTitle } : page.data.title;
  const description = home ? homeDescription : page.data.description;
  // The same pages are served from two Pages sites: both name the Iconem one as the original.
  const url = `${canonicalHost}${basePath}${page.url === '/' ? '/' : `${page.url}/`}`;
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: { title: home ? homeTitle : page.data.title, description, url, siteName: 'OGC 3D Tiles for Blender', type: 'website', images: [`${canonicalHost}${basePath}/img/slides-blender-3dtiles.jpg`] },
    twitter: { card: 'summary_large_image' },
  };
}
