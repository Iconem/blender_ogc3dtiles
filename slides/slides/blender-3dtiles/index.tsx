import { type DesignSystem, type Page, type SlideMeta, useSlidePageNumber } from '@open-slide/core';
import type { CSSProperties, ReactNode } from 'react';

import rome from '@assets/img/rome_google_3dtiles.jpg';
import sidebar from '@assets/img/sidebar.jpg';
import overlays from '@assets/img/raster_overlays.jpg';
import place from '@assets/img/place_search.jpg';
import globe from '@assets/img/globe_osm.jpg';
import tileMaterial from '@assets/img/nodes_tile_material.jpg';
import relight from '@assets/img/nodes_relight.jpg';
import compositor from '@assets/img/nodes_compositor.jpg';
import classes from '@assets/img/metadata_classes.jpg';
import ramp from '@assets/img/metadata_ramp.jpg';
import splats from '@assets/img/splat_tiles.jpg';

// --- Deck kit (the look of the open-geodata-catalog and terrain-viewer decks) ---
// White, hairline rules, soft panels, one accent. Screenshots are the repository's docs/img, copied in by
// scripts/sync-assets.mjs.

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
const FOOT = `OGC 3D Tiles for Blender · ${SITE}`;

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
// the screenshots' own ratio: a frame of this ratio shows one whole
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
}: {
  src: string;
  caption?: string;
  width?: number;
  height?: number;
  position?: string;
}) => (
  <figure style={{ margin: 0, width, flex: 'none' }}>
    <img
      src={src}
      style={{
        width,
        height: height ?? Math.round(width * SHOT_RATIO),
        objectFit: 'cover',
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

const Stat = ({ n, label }: { n: ReactNode; label: ReactNode }) => (
  <div style={{ flex: 1, minWidth: 0, borderTop: `1px solid ${ink.rule}`, paddingTop: 20 }}>
    <div style={{ fontSize: 56, fontWeight: 500, letterSpacing: '-0.035em', lineHeight: 1, color: ink.text }}>{n}</div>
    <div style={{ marginTop: 12, fontSize: 20, color: ink.muted, lineHeight: 1.3 }}>{label}</div>
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


// --- Pages ---

const P01Cover: Page = () => (
  <Cover
    img={rome}
    eyebrow="Blender extension · cesium-native inside"
    title={<>3D Tiles, streamed into Blender</>}
    subtitle="Meshes, point clouds, Gaussian splats and voxels load around the camera, the way Cesium does it, and render in EEVEE and Cycles."
  />
);

const P02Why: Page = () => (
  <Frame eyebrow="Why" title="Two crowds, one missing bridge">
    <div style={{ display: 'flex', gap: 32 }}>
      <Card title="Blender users">
        City models, drone photogrammetry and LiDAR surveys are far larger than a .blend can hold. Importing one tile
        at a time means choosing a level of detail by hand, for every shot.
      </Card>
      <Card title="The 3D Tiles and Cesium crowd">
        Tilesets stream in CesiumJS, Unreal and Unity. Path-traced stills, node-based shading, compositing and
        animation tools were out of reach without exporting.
      </Card>
    </div>
    <div style={{ marginTop: 44 }}>
      <Bullets>
        <Li k="The bridge">a Blender extension that streams a tileset.json as Blender objects, level of detail included.</Li>
        <Li k="Same engine">cesium-native selects, loads and decodes the tiles, as in Cesium for Unreal and Unity.</Li>
        <Li k="Open source">MIT, on GitHub, with a pure Python backend when the native wheel is not installed.</Li>
      </Bullets>
    </div>
  </Frame>
);

const P03How: Page = () => (
  <Frame eyebrow="How it works" title="The viewport is the camera cesium-native follows">
    <TwoCol
      leftWidth={820}
      left={
        <Bullets>
          <Li k="Every tick">the add-on hands the viewport (or the render camera) to cesium-native as a view state.</Li>
          <Li k="Selection">screen-space error, frustum culling, REPLACE and ADD refinement, load priorities.</Li>
          <Li k="Loading">tiles are decoded off the main thread and built as meshes from numpy arrays.</Li>
          <Li k="Unloading">tiles out of view are hidden, then freed; a disk cache keeps the downloads.</Li>
          <Li k="Georeference">a scene origin on the globe; ECEF becomes local east, north, up in metres.</Li>
        </Bullets>
      }
      right={<Shot src={rome} width={820} height={660} caption="Google Photorealistic 3D Tiles over the Colosseum, streamed in the viewport" />}
    />
  </Frame>
);

const P04Content: Page = () => (
  <Frame eyebrow="What streams" title="The flavours of 3D Tiles cesium-native reads">
    <div style={{ display: 'flex', gap: 28 }}>
      <Card title="Meshes">b3dm and glb, with Draco, meshopt and KTX2. 3D Tiles 1.0 and 1.1, implicit tiling included.</Card>
      <Card title="Point clouds">pnts and glTF points, with their colours, intensity and classification.</Card>
    </div>
    <div style={{ display: 'flex', gap: 28, marginTop: 28 }}>
      <Card title="Gaussian splats">KHR_gaussian_splatting, SPZ or uncompressed, as native Blender 5.3 splats.</Card>
      <Card title="Voxels">box and region voxel tiles, as blocks or as OpenVDB volumes.</Card>
    </div>
    <div style={{ marginTop: 40 }}>
      <Bullets size={25}>
        <Li k="Sources">any tileset.json URL, local and network files, Cesium ion assets, Google Photorealistic 3D Tiles.</Li>
        <Li k="Also">a bare WGS84 globe to drape imagery on, and quantized-mesh terrain.</Li>
      </Bullets>
    </div>
  </Frame>
);

const P05Sidebar: Page = () => (
  <Frame eyebrow="In Blender" title="One sidebar tab: add a URL, press Start">
    <TwoCol
      leftWidth={760}
      left={
        <Bullets>
          <Li k="Tilesets">a list of entries, each with its overlays and its clipping; several stream at once.</Li>
          <Li k="Scene origin">automatic, typed in, or found by searching a place name.</Li>
          <Li k="LOD / Streaming">maximum screen-space error, parallel downloads, imports per tick.</Li>
          <Li k="Nodes">material, geometry, compositing and metadata, each one shared by every tile.</Li>
          <Li k="Render">wait for the tiles of each frame before rendering it.</Li>
        </Bullets>
      }
      right={<Shot src={sidebar} width={654} height={730} position="50% 0%" />}
    />
  </Frame>
);

const P06Overlays: Page = () => (
  <Frame eyebrow="Raster overlays" title="Imagery draped on any tileset, as in Cesium">
    <TwoCol
      leftWidth={760}
      left={
        <Bullets>
          <Li k="Sources">URL templates, TMS, WMTS, WMS, Cesium ion, Bing Maps, Google Map Tiles.</Li>
          <Li k="Presets">OpenStreetMap, Esri World Imagery and IGN orthophotos need no key.</Li>
          <Li k="Projection">cesium-native computes the texture coordinates per tile, in the overlay's own tiling scheme.</Li>
          <Li k="Live">tick an overlay or change its opacity while streaming. Several stack in order.</Li>
          <Li k="Point clouds too">each point takes the colour of the map under it.</Li>
        </Bullets>
      }
      right={<Shot src={overlays} width={820} height={461} position="50% 0%" caption="OpenStreetMap draped on Google Photorealistic 3D Tiles over the Colosseum" />}
    />
  </Frame>
);

const P07Origin: Page = () => (
  <Frame eyebrow="Georeference" title="The scene origin sits on the globe">
    <div style={{ display: 'flex', gap: 40 }}>
      <Shot src={place} width={820} height={461} caption="Search place: the origin on the ground at the place found, terrain and geoid heights included" />
      <Shot src={globe} width={820} height={461} caption="A WGS84 globe entry with an OpenStreetMap overlay, over Rome" />
    </div>
    <div style={{ marginTop: 26 }}>
      <Bullets size={25}>
        <Li k="Several tilesets">share one origin, so a drone scan lands inside the city model around it.</Li>
        <Li k="Metres, Z up">Blender units stay metres; coordinates near the origin stay small and precise.</Li>
      </Bullets>
    </div>
  </Frame>
);

const P08Clipping: Page = () => (
  <Frame eyebrow="Clipping" title="Cut a tileset with Blender objects">
    <TwoCol
      leftWidth={860}
      left={
        <Bullets>
          <Li k="Clip-polygons">the outline of a mesh or curve seen from above, as Cesium's clipping polygons.</Li>
          <Li k="Boxes">an object's bounding box, to cut in 3D: the top floors of a building, a slab of a point cloud.</Li>
          <Li k="Viewport region">Blender's Alt+B region, honoured in Material Preview and Rendered too.</Li>
          <Li k="Live">move or keyframe the object and the cut follows, on meshes, points and splats.</Li>
          <Li k="Why">drop a high-resolution scan into a coarser city model without the two overlapping.</Li>
        </Bullets>
      }
      right={
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <Card title="Tiles fully outside">are never downloaded: cesium-native excludes them during selection.</Card>
          <Card title="Tiles on the edge">are cut in the shader, and optionally in the geometry for Solid view and exports.</Card>
          <Card title="Upstream">geometry-level clipping in cesium-native is requested in issue 1486.</Card>
        </div>
      }
    />
  </Frame>
);

const P09Graphs: Page = () => (
  <Frame eyebrow="One graph for all tiles" title="Edit one node group, every tile follows">
    <div style={{ display: 'flex', gap: 40 }}>
      <Shot src={tileMaterial} width={820} height={525} caption="A tile's own material: its texture, then the shared groups in a row" />
      <Shot src={relight} width={820} height={525} caption="OGC3D Relight, the shared shader group: albedo, baked light, roughness, X-ray" />
    </div>
    <div style={{ marginTop: 22 }}>
      <Bullets size={25}>
        <Li k="Shader, geometry, compositor">three shared graphs, applied to tiles already loaded and to those that stream in later.</Li>
      </Bullets>
    </div>
  </Frame>
);

const P10Metadata: Page = () => (
  <Frame eyebrow="Feature metadata" title="Colour by class or by number">
    <div style={{ display: 'flex', gap: 40 }}>
      <Shot src={classes} width={820} height={519} caption="swissBUILDINGS3D over Bern by building type, one editable colour per class" />
      <Shot src={ramp} width={820} height={519} caption="The same tiles by building height, through a colour ramp" />
    </div>
    <div style={{ marginTop: 22 }}>
      <Bullets size={25}>
        <Li k="Read from">feature tables, per-point attributes, property textures and tileset metadata.</Li>
        <Li k="LiDAR">classification gets the LAS names and colours; each class has an opacity, to hide the ground.</Li>
      </Bullets>
    </div>
  </Frame>
);

const P11Splats: Page = () => (
  <Frame eyebrow="Gaussian splats" title="Splat tilesets as native Blender 5.3 splats">
    <TwoCol
      leftWidth={760}
      left={
        <Bullets>
          <Li k="Format">KHR_gaussian_splatting in glTF tiles, SPZ compressed or plain accessors.</Li>
          <Li k="Level of detail">the tileset's own hierarchy: coarse splats far away, fine ones up close.</Li>
          <Li k="Render">EEVEE viewport and Cycles, next to meshes and point clouds.</Li>
          <Li k="Clipping">the same polygons and boxes cut splats.</Li>
          <Li k="Before 5.3">splat tiles show as points.</Li>
        </Bullets>
      }
      right={<Shot src={splats} width={820} height={461} position="50% 63.4%" caption="A splat tileset in Blender 5.3, Rendered viewport" />}
    />
  </Frame>
);

const P12Converged: Page = () => (
  <Frame eyebrow="Animations" title="Each frame waits for its tiles">
    <TwoCol
      leftWidth={860}
      left={
        <Bullets>
          <Li k="The problem">Blender cannot pause inside a render: streaming stops while a frame renders.</Li>
          <Li k="Stream for the camera">tiles are selected for the scene camera, at the render resolution.</Li>
          <Li k="Render converged animation">steps through the frame range and renders each frame itself.</Li>
          <Li k="Settle">a frame renders once the queue is empty and nothing has changed for a moment.</Li>
          <Li k="Output">one file per frame in the scene's output path, as Render Animation does.</Li>
        </Bullets>
      }
      right={
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <Card title="Warm-up">the first frame waits longer: empty scene, cold cache.</Card>
          <Card title="Max wait">a ceiling per frame, so a slow tile never stalls the whole render.</Card>
          <Card title="Finer than the viewport">lower Max SSE before rendering for more detail than you navigate with.</Card>
        </div>
      }
    />
  </Frame>
);

const P13Render: Page = () => (
  <Frame eyebrow="Rendering" title="EEVEE and Cycles, with the look you choose">
    <TwoCol
      leftWidth={800}
      left={
        <Bullets>
          <Li k="Beauty compositor">eye-dome lighting, normal creases, ambient occlusion, haze, a grade.</Li>
          <Li k="Relight">photogrammetry carries its own light: mix it with real lamps, or go clay.</Li>
          <Li k="Orthographic">plans and elevations select the same tiles as a perspective view of that frame.</Li>
          <Li k="X-ray and clay">fade the faces turned to the viewer, or drop the photo for a clay colour.</Li>
        </Bullets>
      }
      right={<Shot src={compositor} width={820} height={475} caption="OGC3D Beauty, the compositor tree built by the add-on" />}
    />
  </Frame>
);

const P14Cesium: Page = () => (
  <Frame eyebrow="For the 3D Tiles crowd" title="What sits between cesium-native and Blender">
    <div style={{ borderBottom: `1px solid ${ink.rule}` }}>
      <Row w={330} k="cesium-native-python" v="the bindings by Caleb Buffa. The add-on installs a wheel built for Blender's own Python, no compiler needed." />
      <Row w={330} k="IPrepareRendererResources" v="implemented in Python: glTF models become numpy arrays in the load thread, Blender meshes in the main thread." />
      <Row w={330} k="Tile excluders" v="clipping polygons and boxes exclude whole tiles before they are downloaded." />
      <Row w={330} k="Raster overlays" v="cesium-native's own, with the overlay texture coordinates read back into Blender materials." />
      <Row w={330} k="Caching" v="cesium-native's sqlite HTTP cache, shared between tilesets, with a size cap." />
      <Row w={330} k="Fallback" v="a pure Python traversal with the same selection rules, when the wheel is absent." />
      <Row w={330} k="Wheels" v="Linux x86_64, Windows x64 and macOS arm64, CPython 3.11 to 3.13, built by GitHub Actions." />
    </div>
  </Frame>
);

const P15Close: Page = () => (
  <div style={fill}>
    <Mark />
    <Eyebrow>OGC 3D Tiles for Blender</Eyebrow>
    <h1 style={{ position: 'absolute', left: PAD_X, top: 220, margin: 0, fontFamily: font.display, fontSize: 112, fontWeight: 500, letterSpacing: '-0.04em', lineHeight: 1 }}>
      Paste a tileset URL.
      <br />
      <span style={{ color: 'var(--osd-accent)' }}>Press Start.</span>
    </h1>
    <div style={{ position: 'absolute', left: PAD_X, right: PAD_X, top: 580, borderBottom: `1px solid ${ink.rule}` }}>
      <CloseLine n={1}>github.com/{OWNER}/blender_ogc3dtiles · the extension zip is on the Releases page</CloseLine>
      <CloseLine n={2}>{SITE} · the documentation</CloseLine>
      <CloseLine n={3}>Blender 4.2 or newer · splats need 5.3</CloseLine>
      <CloseLine n={4}>MIT licence · issues and pull requests welcome</CloseLine>
    </div>
    <Footer />
  </div>
);

export const notes: (string | undefined)[] = [
  `A Blender extension that streams OGC 3D Tiles. The engine is cesium-native, the one behind Cesium for Unreal and Unity.`,
  `Blender users cannot open a city. The 3D Tiles crowd cannot path-trace or composite a tileset. This is the bridge between the two.`,
  `Each tick the viewport becomes a cesium-native view state. Selection, loading and unloading are cesium-native's; the add-on turns the result into Blender objects.`,
  `Everything cesium-native reads: meshes, point clouds, splats, voxels, from a URL, a local file, ion or Google.`,
  `One sidebar tab. Add an entry, paste a URL, press Start.`,
  `Raster overlays the way Cesium for Unreal does them, with presets that need no key.`,
  `The scene origin anchors Blender's local frame on the globe. Several tilesets share it.`,
  `Clipping with Blender objects, live. Tiles fully outside are never downloaded.`,
  `Three shared graphs: shader, geometry, compositor. Edit one, every tile follows.`,
  `Metadata as colours: classes with a palette, numbers with a ramp. LiDAR classes get their usual names and an opacity each.`,
  `Splat tilesets as native Blender 5.3 splats, with their level of detail.`,
  `Blender cannot pause a render to wait for tiles. The converged animation steps through the frames itself and renders each one once its tiles are in.`,
  `Rendering: relight, the beauty compositor for edges, AO and haze, and orthographic views.`,
  `For those who know cesium-native: what the add-on implements on top of the Python bindings.`,
  `Install the zip, paste a URL, press Start. Docs and source at the addresses on screen.`,
];

export const meta: SlideMeta = {
  title: '3D Tiles, streamed into Blender',
  createdAt: '2026-11-05T12:00:00.000Z',
};

export default [
  P01Cover,
  P02Why,
  P03How,
  P04Content,
  P05Sidebar,
  P06Overlays,
  P07Origin,
  P08Clipping,
  P09Graphs,
  P10Metadata,
  P11Splats,
  P12Converged,
  P13Render,
  P14Cesium,
  P15Close,
] satisfies Page[];
