import { notFound } from 'next/navigation';
import type { Metadata } from 'next';
import { DocsBody, DocsDescription, DocsPage, DocsTitle } from 'fumadocs-ui/layouts/docs/page';
import { createRelativeLink } from 'fumadocs-ui/mdx';
import { source } from '@/lib/source';
import { getMDXComponents } from '@/components/mdx';
import { ownHost } from '@/lib/shared';

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
        <MDX components={getMDXComponents({ a: (props) => <RelativeLink {...props} href={ownHost(props.href)} /> })} />
      </DocsBody>
    </DocsPage>
  );
}

export async function generateStaticParams() {
  return source.generateParams();
}

export async function generateMetadata(props: { params: Promise<{ slug?: string[] }> }): Promise<Metadata> {
  const { slug } = await props.params;
  const page = source.getPage(slug);
  if (!page) notFound();

  // The landing page IS the site, so it takes the bare name rather than the "%s — Open Geodata Catalog" template
  // (which would otherwise render "Open Geodata Catalog — Open Geodata Catalog").
  const title = page.url === '/' ? { absolute: page.data.title } : page.data.title;
  return { title, description: page.data.description };
}
