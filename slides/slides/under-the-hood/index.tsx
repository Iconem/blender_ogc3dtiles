import { type DesignSystem, type Page, type SlideMeta, useSlidePageNumber } from '@open-slide/core';
import type { CSSProperties, ReactNode } from 'react';
import { shot } from '@assets/shots';

// --- Deck kit (the same in both decks of this repository, and the look of the open-geodata-catalog and
// terrain-viewer decks) ---
// White, hairline rules, soft panels, one accent. Screenshots are the repository's docs/img, by URL (assets/shots.ts).

const lodCamera = shot('lod_camera_view.jpg');
const metadataNodes = shot('nodes_metadata.jpg');
const relight = shot('nodes_relight.jpg');

export const design: DesignSystem = {
  palette: { bg: '#ffffff', text: '#0a0a0a', accent: '#C2570A' },
  fonts: {
    display: '"Geist Variable", Geist, -apple-system, BlinkMacSystemFont, "Inter", system-ui, sans-serif',
    body: '"Geist Variable", Geist, -apple-system, BlinkMacSystemFont, "Inter", system-ui, sans-serif',
  },
  typeScale: { hero: 140, body: 30 },
  radius: 12,
};

// The repository is on two accounts, each with its own Pages site: the deploy passes the owner it builds for.
const OWNER = ((import.meta as { env?: Record<string, string | undefined> }).env?.VITE_PAGES_OWNER || 'jo-chemla').toLowerCase();
const SITE = `${OWNER}.github.io/blender_ogc3dtiles`;
const FOOT = 'OGC 3D Tiles Streaming · under the hood';

const ink = {
  text: '#0a0a0a',
  soft: '#404040',
  muted: '#6b6b6b',
  dim: '#a3a3a3',
  rule: '#e4e4e4',
  panel: '#f7f7f7',
  red: '#dc2626',
  amber: '#d97706',
  mint: '#1f9e6e',
  violet: '#7c3aed',
};

const font = {
  display: 'var(--osd-font-display)',
  mono: '"Geist Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace',
};

const shadow = {
  edge: '0 0 0 1px rgba(0, 0, 0, 0.06), 0 1px 0 rgba(0, 0, 0, 0.025)',
  window: '0 0 0 1px rgba(0, 0, 0, 0.07), 0 1px 2px rgba(0, 0, 0, 0.04), 0 12px 32px -12px rgba(0, 0, 0, 0.12)',
};

const pad2 = (n: number) => String(n).padStart(2, '0');
const PAD_X = 120;
const SHOT_RATIO = 9 / 16;

const fill: CSSProperties = {
  width: '100%',
  height: '100%',
  position: 'relative',
  overflow: 'hidden',
  background: 'var(--osd-bg)',
  color: 'var(--osd-text)',
  fontFamily: 'var(--osd-font-body)',
  letterSpacing: '-0.01em',
  WebkitFontSmoothing: 'antialiased',
};

const Mark = () => (
  <div style={{ position: 'absolute', left: PAD_X, top: 101, width: 16, height: 16, borderRadius: 4, background: 'var(--osd-accent)' }} />
);

const Footer = () => {
  const { current, total } = useSlidePageNumber();
  return (
    <div
      style={{
        position: 'absolute',
        left: PAD_X,
        right: PAD_X,
        bottom: 44,
        display: 'flex',
        justifyContent: 'space-between',
        fontFamily: font.mono,
        fontSize: 20,
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        color: ink.muted,
      }}
    >
      <span>{FOOT}</span>
      <span>
        {pad2(current)} / {pad2(total)}
      </span>
    </div>
  );
};

const Eyebrow = ({ children }: { children: ReactNode }) => (
  <div style={{ position: 'absolute', left: PAD_X + 28, top: 96, fontSize: 22, lineHeight: '26px', fontWeight: 500, color: 'var(--osd-accent)' }}>
    {children}
  </div>
);

const Frame = ({ eyebrow, title, children }: { eyebrow: string; title: ReactNode; children: ReactNode }) => (
  <div style={fill}>
    <Mark />
    <Eyebrow>{eyebrow}</Eyebrow>
    <h2
      style={{
        position: 'absolute',
        left: PAD_X,
        right: PAD_X,
        top: 138,
        margin: 0,
        fontFamily: font.display,
        fontSize: 60,
        fontWeight: 500,
        letterSpacing: '-0.03em',
        lineHeight: 1.06,
        whiteSpace: 'nowrap',
      }}
    >
      {title}
    </h2>
    <div style={{ position: 'absolute', left: PAD_X, right: PAD_X, top: 250, bottom: 84 }}>{children}</div>
    <Footer />
  </div>
);

const Bullets = ({ children, size = 27 }: { children: ReactNode; size?: number }) => (
  <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', fontSize: size, lineHeight: 1.38, borderBottom: `1px solid ${ink.rule}` }}>
    {children}
  </ul>
);

const Li = ({ children, k }: { children: ReactNode; k?: ReactNode }) => (
  <li style={{ padding: '11px 0', borderTop: `1px solid ${ink.rule}` }}>
    {k ? <span style={{ fontWeight: 500, color: ink.text }}>{k} </span> : null}
    <span style={{ color: k ? ink.soft : ink.text }}>{children}</span>
  </li>
);

const Shot = ({
  src,
  caption,
  width = 900,
  height,
  position = '50% 50%',
  fit = 'cover',
}: {
  src: string;
  caption?: string;
  width?: number;
  height?: number;
  position?: string;
  fit?: CSSProperties['objectFit'];
}) => (
  <figure style={{ margin: 0, width, flex: 'none' }}>
    <img
      src={src}
      style={{
        width,
        height: height ?? Math.round(width * SHOT_RATIO),
        objectFit: fit,
        objectPosition: position,
        borderRadius: 12,
        boxShadow: shadow.window,
        display: 'block',
        background: ink.panel,
      }}
    />
    {caption ? <figcaption style={{ fontSize: 20, color: ink.muted, marginTop: 14, lineHeight: 1.35 }}>{caption}</figcaption> : null}
  </figure>
);

const TwoCol = ({ left, right, leftWidth = 700 }: { left: ReactNode; right: ReactNode; leftWidth?: number }) => (
  <div style={{ display: 'flex', gap: 48, alignItems: 'flex-start' }}>
    <div style={{ width: leftWidth, flex: 'none' }}>{left}</div>
    <div style={{ flex: 1, minWidth: 0 }}>{right}</div>
  </div>
);

const Card = ({ title, children, accent = 'var(--osd-accent)' }: { title: ReactNode; children: ReactNode; accent?: string }) => (
  <div style={{ background: ink.panel, borderRadius: 12, padding: '22px 26px', flex: 1, minWidth: 0 }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 25, fontWeight: 500, letterSpacing: '-0.02em', marginBottom: 8 }}>
      <span style={{ width: 10, height: 10, borderRadius: 3, background: accent, flex: 'none' }} />
      <span>{title}</span>
    </div>
    <div style={{ fontSize: 21, lineHeight: 1.42, color: ink.soft }}>{children}</div>
  </div>
);

const Code = ({ children, size = 21 }: { children: ReactNode; size?: number }) => (
  <pre
    style={{
      margin: 0,
      fontFamily: font.mono,
      fontSize: size,
      lineHeight: 1.5,
      background: ink.panel,
      borderRadius: 12,
      padding: '18px 24px',
      color: ink.soft,
      whiteSpace: 'pre-wrap',
      wordBreak: 'break-word',
    }}
  >
    {children}
  </pre>
);

const Row = ({ k, v, w = 230 }: { k: ReactNode; v: ReactNode; w?: number }) => (
  <div style={{ display: 'flex', gap: 24, padding: '11px 0', borderTop: `1px solid ${ink.rule}`, fontSize: 23, lineHeight: 1.35 }}>
    <span style={{ width: w, flex: 'none', fontWeight: 500, color: ink.text }}>{k}</span>
    <span style={{ color: ink.soft }}>{v}</span>
  </div>
);

const Cover = ({ img, eyebrow, title, subtitle }: { img: string; eyebrow: string; title: ReactNode; subtitle: ReactNode }) => (
  <div style={fill}>
    <Mark />
    <Eyebrow>{eyebrow}</Eyebrow>
    <div style={{ position: 'absolute', left: PAD_X, top: 290, width: 880 }}>
      <h1 style={{ fontFamily: font.display, fontSize: 112, fontWeight: 500, letterSpacing: '-0.04em', lineHeight: 1, margin: 0 }}>{title}</h1>
      <p style={{ fontSize: 30, color: ink.soft, margin: '40px 0 0', maxWidth: 820, lineHeight: 1.45 }}>{subtitle}</p>
    </div>
    <img
      src={img}
      style={{
        position: 'absolute',
        left: 1060,
        top: 200,
        width: 740,
        height: 596,
        objectFit: 'cover',
        objectPosition: '50% 50%',
        borderRadius: 12,
        boxShadow: shadow.window,
        display: 'block',
        background: ink.panel,
      }}
    />
    <Footer />
  </div>
);

const CloseLine = ({ n, children }: { n: number; children: ReactNode }) => (
  <div style={{ display: 'flex', gap: 40, alignItems: 'baseline', padding: '18px 0', borderTop: `1px solid ${ink.rule}`, fontFamily: font.mono, fontSize: 26, color: ink.soft }}>
    <span style={{ fontSize: 20, color: 'var(--osd-accent)', letterSpacing: '0.08em' }}>{pad2(n)}</span>
    <span>{children}</span>
  </div>
);

// Diagram pieces: a stage, and the arrow between two.
const Box = ({ children, sub, accent = 'var(--osd-accent)', w = 360 }: { children: ReactNode; sub?: ReactNode; accent?: string; w?: number }) => (
  <div style={{ width: w, flex: 'none', background: '#fff', boxShadow: shadow.edge, borderTop: `3px solid ${accent}`, borderRadius: 12, padding: '16px 18px', textAlign: 'center' }}>
    <div style={{ fontSize: 23, fontWeight: 500, lineHeight: 1.25 }}>{children}</div>
    {sub ? <div style={{ fontSize: 18, color: ink.muted, marginTop: 6, lineHeight: 1.3 }}>{sub}</div> : null}
  </div>
);

const Arrow = () => <div style={{ color: ink.dim, fontSize: 30, alignSelf: 'center', flex: 'none' }}>→</div>;

const Stat = ({ n, label }: { n: ReactNode; label: ReactNode }) => (
  <div style={{ flex: 1, minWidth: 0, borderTop: `1px solid ${ink.rule}`, paddingTop: 20 }}>
    <div style={{ fontSize: 56, fontWeight: 500, letterSpacing: '-0.035em', lineHeight: 1, color: ink.text }}>{n}</div>
    <div style={{ marginTop: 12, fontSize: 20, color: ink.muted, lineHeight: 1.3 }}>{label}</div>
  </div>
);

const Lane = ({ label, children }: { label: string; children: ReactNode }) => (
  <div style={{ marginBottom: 34 }}>
    <div style={{ fontFamily: font.mono, fontSize: 18, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--osd-accent)', marginBottom: 14 }}>{label}</div>
    <div style={{ display: 'flex', gap: 14, alignItems: 'stretch' }}>{children}</div>
  </div>
);

// --- Pages ---

const P01Cover: Page = () => (
  <Cover
    img={lodCamera}
    eyebrow="OGC 3D Tiles Streaming"
    title="Under the hood"
    subtitle="How a Blender viewport becomes a cesium-native view state, and how the tiles that come back become Blender objects."
  />
);

const P02Stack: Page = () => (
  <Frame eyebrow="The stack" title="Three layers, one tick every 50 ms">
    <Lane label="Blender (bpy)">
      <Box w={510} sub="viewport matrices, resolution">3D viewport</Box>
      <Arrow />
      <Box w={510} sub="list, Max SSE, origin">scene.ogc3dtiles</Box>
      <Arrow />
      <Box w={510} sub="GUI timer, or stream_tick() in -b">modal operator</Box>
    </Lane>
    <Lane label="The add-on (Python)">
      <Box w={510} sub="ENU to ECEF, frustum, ortho">camera adapter</Box>
      <Arrow />
      <Box w={510} sub="numpy arrays, packed images">tile builder</Box>
      <Arrow />
      <Box w={510} sub="show, hide, free in one batch">visibility, eviction</Box>
    </Lane>
    <Lane label="cesium-native-python">
      <Box w={510} sub="update_view(ViewState)" accent={ink.mint}>Tileset</Box>
      <Arrow />
      <Box w={510} sub="IPrepareRendererResources" accent={ink.mint}>tile preparer</Box>
      <Arrow />
      <Box w={510} sub="sqlite HTTP cache, one per process" accent={ink.mint}>asset accessor</Box>
    </Lane>
  </Frame>
);

const P03Tick: Page = () => (
  <Frame eyebrow="One tick" title="What the modal operator does, in order">
    <TwoCol
      leftWidth={900}
      left={
        <Bullets size={25}>
          <Li k="1. Drain">worker results: external tilesets grafted, ready tiles queued.</Li>
          <Li k="2. Build">at most Imports / tick tiles: numpy payload to mesh, glTF importer as fallback.</Li>
          <Li k="3. Select">again only when the view changed, something arrived, or 0.5 s passed.</Li>
          <Li k="4. Load">in priority order, largest screen-space error first, up to the download limit.</Li>
          <Li k="5. Evict">least recently wanted hidden tiles above Max Tiles, in one batch_remove.</Li>
        </Bullets>
      }
      right={
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <Card title="Main thread">everything that touches bpy: meshes, materials, rasters, deletes, selection.</Card>
          <Card title="Worker threads" accent={ink.mint}>downloads and glTF decoding, in cesium-native's pool.</Card>
          <Card title="While navigating" accent={ink.violet}>a build budget in ms, so orbiting stays fluid; loading catches up when you stop.</Card>
        </div>
      }
    />
  </Frame>
);

const P04Busy: Page = () => (
  <Frame eyebrow="Cost" title="What keeps Blender busy while streaming">
    <div style={{ display: 'flex', gap: 32 }}>
      <Stat n="87 ms" label="redraw interval, streaming, default budget" />
      <Stat n="36 ms" label="streaming, view moving (8 ms build budget)" />
      <Stat n="10 ms" label="stopped, Solid shading" />
      <Stat n="~20 ms" label="cesium-native selection per update" />
    </div>
    <div style={{ marginTop: 52 }}>
      <Bullets size={25}>
        <Li k="Measured">on Google Photorealistic 3D Tiles over Rome, about 550 tiles on screen, Blender 5.3.</Li>
        <Li k="12 ms per import">so Imports / tick is the budget when the view rests; 1 keeps the viewport smooth.</Li>
        <Li k="One batch_remove">per tick: deleting objects one by one is quadratic in their number.</Li>
        <Li k="Raster detail">trades imagery resolution for fewer downloads: a tile shows once all its rasters are in.</Li>
      </Bullets>
    </div>
  </Frame>
);

const P05Backends: Page = () => (
  <Frame eyebrow="Two backends" title="Same contract, two engines in the middle">
    <div style={{ display: 'flex', gap: 32 }}>
      <Card title="cesium-native (recommended)" accent={ink.mint}>
        Tileset.update_view, the add-on's preparer for meshes, points and splats, raster overlays, ion, Google, terrain,
        voxels, excluders for clipping. Needs the wheel.
      </Card>
      <Card title="Pure Python (always there)" accent={ink.violet}>
        traversal.select: SSE, frustum culling, REPLACE and ADD, one sorted load queue. Threads and a keep-alive session
        download; workers unwrap b3dm, cmpt and glb. Mesh tilesets only.
      </Card>
    </div>
    <div style={{ marginTop: 44, borderBottom: `1px solid ${ink.rule}` }}>
      <Row w={300} k="Contract" v="a ViewState in, tiles to show, load and free out; Blender objects built by the same code." />
      <Row w={300} k="No bpy" v="traversal, the native backend and the payload readers import no bpy: tested without Blender." />
      <Row w={300} k="Direct mesh" v="off, tiles go through Blender's glTF importer instead: to compare or work around a tile." />
    </div>
  </Frame>
);

const P06Threads: Page = () => (
  <Frame eyebrow="IPrepareRendererResources" title="Load thread, then main thread">
    <TwoCol
      leftWidth={860}
      left={
        <>
          <Bullets size={25}>
            <Li k="prepare_in_load_thread">a cesium-native Model becomes numpy arrays: positions, normals, UVs, colours, metadata.</Li>
            <Li k="prepare_in_main_thread">queued; the tick turns the payload into a mesh with foreach_set and packed images.</Li>
            <Li k="float64 offsets">tile matrices composed in double precision, meshes kept small near the origin.</Li>
            <Li k="Stop cleanly">the preparer outlives cesium-native's last call, so no pure virtual call on Stop.</Li>
          </Bullets>
          <div style={{ marginTop: 28 }}>
            <Code size={20}>{`tile.mesh.attributes  position normal uv
                      color  _FEATURE_ID_0
tile.material         -> OGC3D Relight
tile.modifiers        -> OGC3D Geometry`}</Code>
          </div>
        </>
      }
      right={<Shot src={relight} width={820} height={525} caption="Every tile material ends in the shared OGC3D Relight group" />}
    />
  </Frame>
);

const P07Groups: Page = () => (
  <Frame eyebrow="Shared node groups" title="Thousands of tiles, one graph per kind">
    <TwoCol
      leftWidth={760}
      left={
        <div style={{ borderBottom: `1px solid ${ink.rule}` }}>
          <Row w={260} k="OGC3D Relight" v="albedo, baked light, roughness, X-ray" />
          <Row w={260} k="OGC3D Clip" v="polygons and boxes, cut or keep" />
          <Row w={260} k="OGC3D Metadata" v="palette, ramp, opacity per class" />
          <Row w={260} k="OGC3D Points" v="point display, size on screen" />
          <Row w={260} k="OGC3D Splats" v="mesh to 3D Gaussian splat points" />
          <Row w={260} k="OGC3D Geometry" v="your Geometry Nodes, on every tile" />
          <Row w={260} k="OGC3D Beauty" v="the compositor tree: EDL, AO, haze" />
        </div>
      }
      right={
        <>
          <Shot src={metadataNodes} width={860} height={550} caption="OGC3D Metadata, wired into each tile's material" />
          <div style={{ marginTop: 24, fontSize: 22, color: ink.soft, lineHeight: 1.4 }}>
            A slider moves one value in one group: no material rebuild, tiles loaded later get it too.
          </div>
        </>
      }
    />
  </Frame>
);

const P08Clip: Page = () => (
  <Frame eyebrow="Clipping" title="Three layers: selection, shader, geometry">
    <div style={{ display: 'flex', gap: 16, alignItems: 'stretch' }}>
      <Box w={520} sub="RasterizedPolygonsTileExcluder, a Python ITileExcluder for boxes" accent={ink.mint}>Tiles fully outside: never loaded</Box>
      <Arrow />
      <Box w={520} sub="OGC3D Clip reads the volumes, keyframes included">Edge tiles: cut per pixel</Box>
      <Arrow />
      <Box w={520} sub="for Solid view, snapping, exports" accent={ink.violet}>Cut Geometry: faces deleted</Box>
    </div>
    <div style={{ marginTop: 48 }}>
      <Bullets size={25}>
        <Li k="Instant modes">cut or keep, any or all: values in the group, not a new shader.</Li>
        <Li k="Points and splats">their own clip group, rebuilt when a clip object is recreated under the same name.</Li>
        <Li k="Upstream">geometry-level clipping in cesium-native, requested in issue 1486.</Li>
      </Bullets>
    </div>
  </Frame>
);

const P09Cameras: Page = () => (
  <Frame eyebrow="View states" title="Every Blender camera, as cesium-native sees it">
    <div style={{ borderBottom: `1px solid ${ink.rule}` }}>
      <Row w={300} k="Perspective" v="position, direction, up, field of view, viewport height in pixels." />
      <Row w={300} k="Orthographic" v="the binding's orthographic ViewState: eye on the pivot, the frame's half extents." />
      <Row w={300} k="Panoramic" v="update_view_group with six 90° cube views, each at the panorama's angular resolution." />
      <Row w={300} k="Fisheye" v="the cube faces outside its field of view dropped: five for 180°." />
      <Row w={300} k="Render camera" v="the render resolution, not the viewport's: what the frame will need." />
    </div>
    <div style={{ marginTop: 36, fontSize: 22, color: ink.muted, lineHeight: 1.4 }}>
      An eye, a culling volume and an error function in one view state is requested upstream: cesium-native#1501.
    </div>
  </Frame>
);

const P10Binding: Page = () => (
  <Frame eyebrow="cesium-native-python" title="The binding, and the wheels it ships as">
    <TwoCol
      leftWidth={860}
      left={
        <Bullets size={25}>
          <Li k="Bindings">by Caleb Buffa: cesium-native's tilesets, view states, raster overlays and excluders in Python.</Li>
          <Li k="Wheels">CPython 3.11 to 3.13, Linux x86_64, Windows x64, macOS arm64, built by cibuildwheel.</Li>
          <Li k="Installer">the add-on preferences fetch the wheel for Blender's own Python, no compiler.</Li>
          <Li k="Upstream">build fixes and the wheel workflow merged; the add-on dropped its own patch.</Li>
        </Bullets>
      }
      right={
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <Card title="Windows">Blender 4.2 to 4.5 bundle an old C++ runtime: the released wheels are built for it.</Card>
          <Card title="Linux" accent={ink.mint}>HTTPS on every distribution: curl reads certifi's CA bundle.</Card>
          <Card title="First build" accent={ink.violet}>vcpkg builds cesium-native's dependencies: hours once, cached after.</Card>
        </div>
      }
    />
  </Frame>
);

const P11Ship: Page = () => (
  <Frame eyebrow="Tests and releases" title="Tested without Blender, released as an extension">
    <div style={{ display: 'flex', gap: 32 }}>
      <Stat n="193" label="pytest test functions: traversal, coordinates, payloads, clipping" />
      <Stat n="0" label="Blender needed to run them" />
      <Stat n="3" label="platforms for the cesium-native wheel" />
    </div>
    <div style={{ marginTop: 52 }}>
      <Bullets size={25}>
        <Li k="CI">pytest on Python 3.11 and 3.13 and ruff on every push; cesium-native tests skip without the wheel.</Li>
        <Li k="Release">a tag builds the zip with Blender's packager, validates it, attaches it to the release.</Li>
        <Li k="Docs and slides">these decks and the docs site, deployed to GitHub Pages on push.</Li>
      </Bullets>
    </div>
  </Frame>
);

const P12Close: Page = () => (
  <div style={fill}>
    <Mark />
    <Eyebrow>OGC 3D Tiles Streaming · under the hood</Eyebrow>
    <h1 style={{ position: 'absolute', left: PAD_X, top: 220, margin: 0, fontFamily: font.display, fontSize: 112, fontWeight: 500, letterSpacing: '-0.04em', lineHeight: 1 }}>
      cesium-native selects.
      <br />
      <span style={{ color: 'var(--osd-accent)' }}>Blender renders.</span>
    </h1>
    <div style={{ position: 'absolute', left: PAD_X, right: PAD_X, top: 580, borderBottom: `1px solid ${ink.rule}` }}>
      <CloseLine n={1}>{SITE}/dev/architecture · modules, data flow, the two backends</CloseLine>
      <CloseLine n={2}>{SITE}/dev/cesium-native · the wheel, versions, upstream requests</CloseLine>
      <CloseLine n={3}>github.com/{OWNER}/blender_ogc3dtiles · source, issues, releases</CloseLine>
    </div>
    <Footer />
  </div>
);

export const notes: (string | undefined)[] = [
  `How the add-on works inside: from the viewport to cesium-native and back to Blender objects.`,
  `Three layers. Blender gives the view and the settings, the add-on translates, cesium-native selects and loads.`,
  `One tick of the modal operator, every 50 ms. Only the main thread touches bpy.`,
  `Where the time goes. Measured on Google tiles over Rome with about 550 tiles on screen.`,
  `Two backends with the same contract. cesium-native is the one to install; the Python one keeps mesh tilesets working without it.`,
  `The tile preparer: decode in cesium-native's load threads, build meshes on the main thread.`,
  `Shared node groups are the design choice that makes thousands of tiles editable as one.`,
  `Clipping happens at three levels: tiles never loaded, pixels cut in the shader, faces deleted for exports.`,
  `Each kind of Blender camera maps to a cesium-native view state; panoramas become six cube views.`,
  `The binding and its wheels. Upstream merged the build fixes.`,
  `Tests run without Blender. A tag builds and validates the extension zip.`,
  `Where to read more.`,
];

export const meta: SlideMeta = {
  title: 'Under the hood',
  createdAt: '2026-11-17T12:00:00.000Z',
};

export default [
  P01Cover,
  P02Stack,
  P03Tick,
  P04Busy,
  P05Backends,
  P06Threads,
  P07Groups,
  P08Clip,
  P09Cameras,
  P10Binding,
  P11Ship,
  P12Close,
] satisfies Page[];
