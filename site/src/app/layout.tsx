import type { Metadata } from 'next';
import { Provider } from '@/components/provider';
import { appName } from '@/lib/shared';
import './global.css';

export const metadata: Metadata = {
  title: { default: appName, template: `%s — ${appName}` },
  description: 'Blender add-on that streams OGC 3D Tiles (Google Photorealistic 3D Tiles, Cesium ion, point clouds, Gaussian splats): user guide, features and developer notes.',
  metadataBase: new URL('https://iconem.github.io'),
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="flex flex-col min-h-screen">
        <Provider>{children}</Provider>
      </body>
    </html>
  );
}
