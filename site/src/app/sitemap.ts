import type { MetadataRoute } from 'next';
import { source } from '@/lib/source';
import { basePath, canonicalHost } from '@/lib/shared';

export const dynamic = 'force-static';

// sitemap.xml of the static export, with the canonical (Iconem) addresses.
export default function sitemap(): MetadataRoute.Sitemap {
  return source.getPages().map((page) => ({
    url: `${canonicalHost}${basePath}${page.url === '/' ? '/' : `${page.url}/`}`,
    changeFrequency: page.url === '/changelog' ? 'weekly' : 'monthly',
    priority: page.url === '/' ? 1 : page.url.startsWith('/guide') ? 0.8 : 0.6,
  }));
}
