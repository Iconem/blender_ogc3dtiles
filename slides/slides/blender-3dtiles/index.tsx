import { type DesignSystem, type Page, type SlideMeta, useSlidePageNumber } from '@open-slide/core';
import type { CSSProperties, ReactNode } from 'react';
import { shot } from '@assets/shots';

// --- Deck kit (the same in both decks of this repository, and the look of the open-geodata-catalog and
// terrain-viewer decks) ---
// White, hairline rules, soft panels, one accent. Screenshots are the repository's docs/img, by URL (assets/shots.ts).

const rome = shot('rome_google_3dtiles.jpg');
const sidebar = shot('sidebar.jpg');
const overlays = shot('raster_overlays.jpg');
const lodCamera = shot('lod_camera_view.jpg');
const lodOutside = shot('lod_outside_render.jpg');
const tileMaterial = shot('nodes_tile_material.jpg');
const relight = shot('nodes_relight.jpg');
const points = shot('nodes_points.jpg');
const clipNodes = shot('nodes_clip.jpg');
const compositor = shot('nodes_compositor.jpg');
const classes = shot('metadata_classes.jpg');
const ramp = shot('metadata_ramp.jpg');
const splats = shot('splat_tiles.jpg');
const voxels = shot('voxel_tilesets.jpg');
const tileColours = shot('tiles_random_google.jpg');
const solidMesh = shot('solid_venice.jpg');
const solidPoints = shot('points_sacre_colour.jpg');
const splatsCycles = shot('splats_baldacchino.jpg');
const gizeh = shot('mesh_gizeh_normal.jpg');
const notreDame = shot('origin_notre_dame.jpg');
const tokyo = shot('origin_tokyo.jpg');
const colosseum = shot('origin_colosseum.jpg');
const canyon = shot('origin_grand_canyon.jpg');
const clay = shot('shader_clay.jpg');
const albedo = shot('shader_albedo.jpg');
const relit = shot('shader_relit.jpg');
const xray = shot('shader_xray.jpg');
const beauty = shot('lidar_classes_ign.jpg');
const edl = shot('lidar_classes_edl_ign.jpg');
const pointsColour = shot('points_geghard.jpg');
const reveal = shot('points_reveal.jpg');
const clipBox = shot('clip_box_colosseum.jpg');
const clipCut = shot('clip_geghard.jpg');
const camPersp = shot('camera_persp.jpg');
const camOrtho = shot('camera_ortho.jpg');
const camPano = shot('camera_pano.jpg');
const camPerspTop = shot('camera_persp_top.jpg');
const camOrthoTop = shot('camera_ortho_top.jpg');
const camPanoTop = shot('camera_pano_top.jpg');
const entryBoxes = shot('panel_boxes_match_to.png');
const matchBefore = shot('giza_match_before.jpg');
const matchAfter = shot('giza_match_after.jpg');
const blendGiza = shot('terrain_blend_giza_view.jpg');
const markersGlobe = shot('markers_globe.jpg');

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
// Source links always point at the Iconem repository.
const OWNER = ((import.meta as { env?: Record<string, string | undefined> }).env?.VITE_PAGES_OWNER || 'iconem').toLowerCase();
const SITE = `${OWNER}.github.io/blender_ogc3dtiles`;
const REPO = 'github.com/Iconem/blender_ogc3dtiles';
const FOOT = `OGC 3D Tiles Streaming · ${SITE}`;

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

// A link that stays clickable in the PDF: the address itself, in the accent colour.
const A = ({ href, children }: { href: string; children?: ReactNode }) => (
  <a href={href.startsWith('http') ? href : `https://${href}`} style={{ color: 'var(--osd-accent)', textDecoration: 'none' }}>
    {children ?? href}
  </a>
);

// Two to four screenshots in a grid, each with a short caption under it.
const Grid = ({ items, cols = 2, width, height }: { items: { src: string; caption: string; position?: string; fit?: CSSProperties['objectFit'] }[]; cols?: number; width: number; height: number }) => (
  <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, ${width}px)`, gap: '18px 28px' }}>
    {items.map((it) => (
      <figure key={it.src} style={{ margin: 0 }}>
        <img
          src={it.src}
          style={{ width, height, objectFit: it.fit ?? 'cover', objectPosition: it.position ?? '50% 50%', borderRadius: 10, boxShadow: shadow.window, display: 'block', background: ink.panel }}
        />
        <figcaption style={{ fontSize: 19, color: ink.muted, marginTop: 8, lineHeight: 1.3 }}>{it.caption}</figcaption>
      </figure>
    ))}
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
    <div style={{ display: 'flex', gap: 16, alignItems: 'stretch' }}>
      <Box w={300} sub="viewport or render camera">Blender view</Box>
      <Arrow />
      <Box w={300} sub="ECEF, frustum, resolution">ViewState</Box>
      <Arrow />
      <Box w={300} sub="select, load, decode" accent={ink.mint}>cesium-native</Box>
      <Arrow />
      <Box w={300} sub="meshes, points, splats" accent={ink.violet}>Blender objects</Box>
    </div>
    <div style={{ marginTop: 48 }}>
      <Bullets>
        <Li k="Every tick">the add-on hands the viewport, or a camera, to cesium-native as a view state.</Li>
        <Li k="Selection">screen-space error, frustum culling, REPLACE and ADD refinement, load priorities.</Li>
        <Li k="Loading">tiles are decoded off the main thread into numpy arrays, then built as meshes.</Li>
        <Li k="Unloading">tiles out of view are hidden, then freed; a disk cache keeps the downloads.</Li>
        <Li k="Binding">cesium-native-python, installed as a wheel built for Blender's own Python.</Li>
      </Bullets>
    </div>
  </Frame>
);

const P04Objects: Page = () => (
  <Frame eyebrow="Tiles as Blender objects" title="Every tile is an object you can see in the outliner">
    <TwoCol
      leftWidth={760}
      left={
        <Bullets>
          <Li k="One root Empty">per tileset, in a 3D Tiles collection: move, rotate, hide or fold it as one.</Li>
          <Li k="Shown, then hidden">a tile stays loaded while it is out of view, until the cap frees it.</Li>
          <Li k="Shared node groups">each tile's material and modifiers point at one graph per kind.</Li>
          <Li k="Your selection">imports never touch the selected or active object.</Li>
          <Li k="Pause">untick a tileset to freeze what is loaded while you look around.</Li>
        </Bullets>
      }
      right={<Shot src={tileColours} width={820} height={480} caption="One colour per tile on Google 3D Tiles around Notre-Dame: each tile is an object, at its own level of detail" />}
    />
  </Frame>
);

const P05Content: Page = () => (
  <Frame eyebrow="What streams" title="The flavours of 3D Tiles cesium-native reads">
    <TwoCol
      leftWidth={700}
      left={
        <Bullets size={24}>
          <Li k="Meshes">b3dm and glb, Draco, meshopt, KTX2. 3D Tiles 1.0 and 1.1, implicit tiling.</Li>
          <Li k="Point clouds">pnts and glTF points, with colours, intensity and classification.</Li>
          <Li k="Gaussian splats">KHR_gaussian_splatting, SPZ or plain, as native Blender 5.3 splats.</Li>
          <Li k="Voxels">box and region voxel tiles, as blocks or as OpenVDB volumes.</Li>
          <Li k="Sources">any tileset.json URL, local and network files, Cesium ion, Google Photorealistic 3D Tiles.</Li>
          <Li k="Also">a bare WGS84 globe to drape imagery on, and quantized-mesh terrain.</Li>
        </Bullets>
      }
      right={
        <Grid
          width={448}
          height={252}
          items={[
            { src: solidMesh, caption: 'Mesh, Solid view: Piazza San Marco, Venice' },
            { src: solidPoints, caption: 'Point cloud, EEVEE: Sacré-Cœur, Paris' },
            { src: splatsCycles, caption: "Gaussian splats, Cycles: Bernini's baldacchino, San Pietro" },
            { src: gizeh, caption: 'Mesh, Solid view with the normal matcap: Khafre and Khufu, Giza' },
          ]}
        />
      }
    />
  </Frame>
);

const P06Sidebar: Page = () => (
  <Frame eyebrow="In Blender" title="One sidebar tab: add a URL, press Start">
    <TwoCol
      leftWidth={760}
      left={
        <Bullets>
          <Li k="Tilesets">a list of entries, each with its overlays and its clipping; several stream at once.</Li>
          <Li k="Scene origin">automatic, typed in, pasted in double precision, or found by place name.</Li>
          <Li k="LOD / Streaming">Max SSE, which camera decides, parallel downloads, tile bounds.</Li>
          <Li k="Nodes">material, geometry, compositing and metadata, each shared by every tile.</Li>
          <Li k="Render">wait for the tiles of each frame before rendering it.</Li>
        </Bullets>
      }
      right={<Shot src={sidebar} width={654} height={730} position="50% 0%" />}
    />
  </Frame>
);

const P07Lod: Page = () => (
  <Frame eyebrow="Level of detail" title="Max SSE sets how fine, a camera sets where">
    <div style={{ display: 'flex', gap: 40 }}>
      <Shot src={lodCamera} width={820} height={480} caption="Through the scene camera that selects the tiles, over the Capitoline Hill" />
      <Shot src={lodOutside} width={820} height={480} caption="The same moment from outside: the camera's view volume and the tiles it selected" />
    </div>
    <div style={{ marginTop: 22 }}>
      <Bullets size={24}>
        <Li k="Max SSE">the error allowed on screen, in pixels: 8 by default. Halve it for the next level of detail.</Li>
        <Li k="Stream for">the 3D viewport, the scene camera at render resolution, or any camera you pick.</Li>
      </Bullets>
    </div>
  </Frame>
);

const P08SeeLod: Page = () => (
  <Frame eyebrow="New in 0.6 and after" title="See the tiles and their levels">
    <div style={{ display: 'flex', gap: 28 }}>
      <Card title="Tile bounds">
        A wire outline per visible tile, in the 3D view only. <i>Tile objects</i> outlines what a tile holds, splats
        included; <i>3D Tiles volumes</i> outlines the boxes, spheres and regions the tileset declares.
      </Card>
      <Card title="Colour by tile level" accent={ink.violet}>
        Through the Color Ramp: depth in the hierarchy, or the geometric error as log2 metres. Shows which level is on
        screen where, and where two levels meet.
      </Card>
      <Card title="Random colour per tile" accent={ink.mint}>
        One of 24 colours per tile, kept when the tile comes back: the tiles themselves, at a glance.
      </Card>
    </div>
    <div style={{ marginTop: 44 }}>
      <Bullets size={25}>
        <Li k="Drag Max SSE">with bounds on, and watch tiles split into finer ones and coarser ones come back.</Li>
        <Li k="Nothing added">the outlines are drawn by the viewport, not objects: they never show in renders.</Li>
        <Li k="Panoramic cameras">select tiles all around them, as six 90° views at the panorama's resolution.</Li>
      </Bullets>
    </div>
  </Frame>
);

const P09Origin: Page = () => (
  <Frame eyebrow="Georeference" title="The scene origin sits on the globe">
    <TwoCol
      leftWidth={1148}
      left={
        <Grid
          width={560}
          height={300}
          items={[
            { src: notreDame, caption: 'Notre-Dame de Paris, looking north' },
            { src: tokyo, caption: 'Tokyo Tower' },
            { src: colosseum, caption: 'The Colosseum, Rome' },
            { src: canyon, caption: 'The Grand Canyon from Yavapai Point' },
          ]}
        />
      }
      right={
        <Bullets size={23}>
          <Li k="Place search">terrain and geoid heights included: the origin lands on the ground.</Li>
          <Li k="Several tilesets">share one origin, so a drone scan lands inside the city model around it.</Li>
          <Li k="Double precision">kept in a scene property: no 0.7 m drift at longitude 150, as with Blender's floats.</Li>
        </Bullets>
      }
    />
  </Frame>
);

const P10Shader: Page = () => (
  <Frame eyebrow="Shared shader · 1 / 3" title="Photo albedo, or clay under real lights">
    <div style={{ display: 'flex', gap: 40 }}>
      <Shot src={albedo} width={820} height={461} caption="Pure albedo: the Bayon's photogrammetry texture, unlit, with eye-dome lighting on top" />
      <Shot src={clay} width={820} height={461} caption="Clay: albedo off, shaded by a sun lamp and a sky" />
    </div>
    <div style={{ marginTop: 26 }}>
      <Bullets size={25}>
        <Li k="OGC3D Relight">one shader group in every tile material, loaded and streamed later.</Li>
        <Li k="Albedo Strength">1 is the photo, 0 is clay: the geometry alone, for reading form and checking a scan.</Li>
      </Bullets>
    </div>
  </Frame>
);

const P11Relight: Page = () => (
  <Frame eyebrow="Shared shader · 2 / 3" title="Relit by your lamps, or seen through the walls">
    <div style={{ display: 'flex', gap: 40 }}>
      <Shot src={relit} width={820} height={461} caption="Relit: the Bayon's photo albedo, mostly lit by the scene's sun and sky" />
      <Shot src={xray} width={820} height={461} caption="X-ray on the San Pietro interior mesh: faces turned to you fade" />
    </div>
    <div style={{ marginTop: 26 }}>
      <Bullets size={25}>
        <Li k="Baked Light">photogrammetry carries its own light: 1 keeps it unlit, 0 lets real lamps shade it.</Li>
        <Li k="X-ray">walls facing the viewer fade, grazing ones stay: plans and interiors read through the shell.</Li>
      </Bullets>
    </div>
  </Frame>
);

const P12Graphs: Page = () => (
  <Frame eyebrow="Shared shader · 3 / 3" title="Edit one node group, every tile follows">
    <div style={{ display: 'flex', gap: 40 }}>
      <Shot src={tileMaterial} width={820} height={525} caption="A tile's own material: its texture, then the shared groups in a row" />
      <Shot src={relight} width={820} height={525} caption="OGC3D Relight, the shared shader group: albedo, baked light, roughness, X-ray" />
    </div>
    <div style={{ marginTop: 22 }}>
      <Bullets size={25}>
        <Li k="Shader, geometry, compositor, metadata">shared graphs, applied to tiles loaded and to those that stream in later.</Li>
      </Bullets>
    </div>
  </Frame>
);

const P13Clipping: Page = () => (
  <Frame eyebrow="Clipping volumes" title="Cut a tileset with Blender objects">
    <div style={{ display: 'flex', gap: 40 }}>
      <Shot src={clipBox} width={820} height={461} caption="Google 3D Tiles kept inside a box around the Colosseum" />
      <Shot src={clipCut} width={820} height={461} caption="A section through the Geghard monastery, Armenia: interior and exterior point clouds, both through 3dtiled" />
    </div>
    <div style={{ marginTop: 26 }}>
      <Bullets size={24}>
        <Li k="Boxes and polygons">an object's bounding box cuts in 3D; a mesh or curve outline cuts from above, as Cesium's clipping polygons.</Li>
        <Li k="Cut or keep, live">inside any or all volumes, switched instantly; move or keyframe the object and the cut follows, on meshes, points and splats.</Li>
      </Bullets>
    </div>
  </Frame>
);

const P14ClipNodes: Page = () => (
  <Frame eyebrow="Clipping volumes" title="Three layers: selection, geometry, shader">
    <TwoCol
      leftWidth={720}
      left={
        <Bullets size={25}>
          <Li k="Never downloaded">tiles fully outside are excluded during selection.</Li>
          <Li k="Cut geometry">faces entirely cut are deleted for Solid view, snapping and exports.</Li>
          <Li k="Shader">edge tiles are cut per pixel by one shared group.</Li>
          <Li k="Viewport region">Blender's Alt+B, honoured in Material Preview and Rendered.</Li>
        </Bullets>
      }
      right={<Shot src={clipNodes} width={912} height={560} caption="OGC3D Clip, the shared group that cuts edge tiles in the shader" />}
    />
  </Frame>
);

const P15Points: Page = () => (
  <Frame eyebrow="Point clouds" title="Points as Geometry Nodes, sized on screen">
    <div style={{ display: 'flex', gap: 40 }}>
      <Shot src={pointsColour} width={820} height={461} caption="The Geghard monastery, interior and exterior point clouds, EEVEE with eye-dome lighting" />
      <Shot src={reveal} width={820} height={461} caption="The height reveal demo, one shared graph on every tile: the monastery builds up from the ground" />
    </div>
    <div style={{ marginTop: 26 }}>
      <Bullets size={25}>
        <Li k="Size">attenuated between 1 and 3 px on screen, so coarse tiles do not show as discs.</Li>
        <Li k="Demo graphs">Suzanne on points, noise displacement, height reveal: edit one graph, every tile follows.</Li>
      </Bullets>
    </div>
  </Frame>
);

const P16PointNodes: Page = () => (
  <Frame eyebrow="Point clouds" title="One display group for every point tile">
    <TwoCol
      leftWidth={760}
      left={
        <Bullets>
          <Li k="Display">points with a shared Geometry Nodes group, in EEVEE and Cycles.</Li>
          <Li k="Colours">RGB, intensity, classification, or the imagery draped over them.</Li>
          <Li k="LiDAR classes">LAS names and colours, one opacity per class: hide the ground.</Li>
          <Li k="Or as">tiny tetrahedra coloured in Solid view, or disc splats along the normals.</Li>
        </Bullets>
      }
      right={<Shot src={points} width={820} height={525} caption="OGC3D Points, the shared point display group" />}
    />
  </Frame>
);

const P17Splats: Page = () => (
  <Frame eyebrow="Gaussian splats" title="Splat tilesets as native Blender 5.3 splats">
    <TwoCol
      leftWidth={760}
      left={
        <Bullets>
          <Li k="Format">KHR_gaussian_splatting in glTF tiles, SPZ compressed or plain accessors.</Li>
          <Li k="Level of detail">the tileset's own hierarchy: coarse splats far away, fine ones up close.</Li>
          <Li k="Converters">EXT_splat_opacity honoured: merged splats keep their source opacity.</Li>
          <Li k="Render">EEVEE viewport and Cycles, next to meshes and point clouds; clipped like them.</Li>
          <Li k="Before 5.3">splat tiles show as points.</Li>
        </Bullets>
      }
      right={<Shot src={splats} width={820} height={461} position="50% 63.4%" caption="A splat tileset in Blender 5.3, Rendered viewport" />}
    />
  </Frame>
);

// LAS classes on the IGN tile, in the add-on's default colours (sRGB of the linear values it uses)
const LAS_LEGEND: [string, string][] = [
  ['Ground', '#c4aa89'],
  ['Low vegetation', '#cbedaa'],
  ['Medium vegetation', '#95da95'],
  ['High vegetation', '#59b36c'],
  ['Building', '#ed9589'],
  ['Water', '#7cb3f3'],
  ['Bridge deck', '#f3e195'],
  ['Unclassified', '#cbcbcb'],
];

const P18Beauty: Page = () => (
  <Frame eyebrow="Point clouds" title="LiDAR classes, read from the tiles">
    <div style={{ display: 'flex', gap: 40 }}>
      <Shot src={beauty} width={820} height={461} caption="IGN LiDAR HD around the Eiffel Tower, coloured by LAS class" />
      <Shot src={edl} width={820} height={461} caption="The same tiles with eye-dome lighting from the beauty compositor" />
    </div>
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px 30px', marginTop: 22, fontSize: 21, color: ink.soft }}>
      {LAS_LEGEND.map(([name, colour]) => (
        <span key={name} style={{ display: 'inline-flex', alignItems: 'center', gap: 10, whiteSpace: 'nowrap' }}>
          <span style={{ width: 18, height: 18, borderRadius: 4, background: colour, display: 'inline-block' }} />
          {name}
        </span>
      ))}
    </div>
    <div style={{ marginTop: 22 }}>
      <Bullets size={24}>
        <Li k="Classes">classification from COPC tiles streamed by 3dtiled, with the LAS names and colours; one editable colour and opacity per class.</Li>
      </Bullets>
    </div>
  </Frame>
);

const P19Render: Page = () => (
  <Frame eyebrow="Rendering" title="EEVEE and Cycles, with the look you choose">
    <TwoCol
      leftWidth={800}
      left={
        <Bullets>
          <Li k="Beauty compositor">one tree built by the add-on, shown in Rendered shading and in renders.</Li>
          <Li k="Atmosphere preset">a sun, a matching sky and haze, in one click.</Li>
          <Li k="Stable viewport">one sample while the compositor is on: no edge shimmer.</Li>
          <Li k="Cycles">path-traced tiles; the compositor drops the passes Cycles has not got in the viewport.</Li>
        </Bullets>
      }
      right={<Shot src={compositor} width={820} height={475} caption="OGC3D Beauty, the compositor tree built by the add-on" />}
    />
  </Frame>
);

const P20Cameras: Page = () => (
  <Frame eyebrow="Cameras · 1 / 2" title="Perspective, orthographic and panoramic">
    <Grid
      cols={3}
      width={541}
      height={304}
      items={[
        { src: camPersp, caption: 'Perspective: the scene camera at render resolution' },
        { src: camOrtho, caption: "Orthographic: a plan of the Colosseum, cesium-native's orthographic view state" },
        { src: camPano, caption: 'Panoramic: equirectangular, rendered by Cycles' },
      ]}
    />
    <div style={{ marginTop: 30 }}>
      <Bullets size={25}>
        <Li k="Perspective">the viewport, the scene camera, or a chosen camera while you navigate freely.</Li>
        <Li k="Orthographic">plans and elevations select the tiles of the frame, behind the pivot too.</Li>
        <Li k="Panoramic">equirectangular, fisheye, cylindrical: six cube views selected together, five for a 180° fisheye.</Li>
      </Bullets>
    </div>
  </Frame>
);

const P21Frustums: Page = () => (
  <Frame eyebrow="Cameras · 2 / 2" title="From above: the tiles each camera asks for">
    <Grid
      cols={3}
      width={541}
      height={304}
      items={[
        { src: camPerspTop, caption: 'Perspective: a wedge, fine near the camera, coarse to the horizon' },
        { src: camOrthoTop, caption: 'Orthographic: exactly the frame, at even detail' },
        { src: camPanoTop, caption: 'Panoramic: tiles all around the camera' },
      ]}
    />
    <div style={{ marginTop: 30 }}>
      <Bullets size={25}>
        <Li k="Top views">one colour per tile; the camera's view volume in white, drawn far longer than its clip range.</Li>
        <Li k="Scrub the timeline">and the tiles follow the camera path, before any render.</Li>
        <Li k="Upstream">a view state with an eye, a culling volume and an error function: cesium-native#1501.</Li>
      </Bullets>
    </div>
  </Frame>
);

const P22Converged: Page = () => (
  <Frame eyebrow="Animations" title="Render converged animation: each frame waits">
    <TwoCol
      leftWidth={860}
      left={
        <Bullets>
          <Li k="The problem">Blender cannot pause inside a render: streaming stops while a frame renders.</Li>
          <Li k="Stream for the camera">tiles are selected for the scene camera, at the render resolution.</Li>
          <Li k="Step by step">the operator moves through the frame range and renders each frame itself.</Li>
          <Li k="Settle">a frame renders once the queue is empty and nothing has changed for a moment.</Li>
          <Li k="Output">one file per frame in the scene's output path, as Render Animation does.</Li>
        </Bullets>
      }
      right={
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <Card title="Warm-up">the first frame waits longer: empty scene, cold cache.</Card>
          <Card title="Max wait">a ceiling per frame, so a slow tile never stalls the whole render.</Card>
          <Card title="Clipping">keyframed clipping volumes are honoured, frame by frame.</Card>
        </div>
      }
    />
  </Frame>
);

const P23Files: Page = () => (
  <Frame eyebrow="Files and export" title="Local tilesets, libraries, copies and exports">
    <div style={{ borderBottom: `1px solid ${ink.rule}` }}>
      <Row w={340} k="Local and network files" v="a folder on disk or a NAS share; network files can go through the disk cache." />
      <Row w={340} k="Disk cache" v="cesium-native's sqlite HTTP cache, shared between tilesets, with a size cap." />
      <Row w={340} k="Tileset libraries" v="JSON files of entries, personal or shared on a NAS, with search and type filters." />
      <Row w={340} k="Copy into project" v="a tileset downloaded into //tilesets/, cropped to an object, down to a chosen error." />
      <Row w={340} k="Cut geometry" v="clipped faces deleted for Solid view, snapping and exports; on by default." />
      <Row w={340} k="Export" v="tiles are plain Blender meshes: any exporter, any modifier." />
    </div>
    <div style={{ marginTop: 28, fontSize: 21, color: ink.muted }}>Keys and share-link tokens are never written into a copy. Google's terms forbid storing its tiles offline.</div>
  </Frame>
);

const P24Overlays: Page = () => (
  <Frame eyebrow="Raster overlays" title="Imagery draped on any tileset, as in Cesium">
    <TwoCol
      leftWidth={760}
      left={
        <Bullets>
          <Li k="Sources">URL templates, TMS, WMTS, WMS, Cesium ion, Bing Maps, Google Map Tiles.</Li>
          <Li k="Presets">OpenStreetMap, Esri World Imagery and IGN orthophotos need no key.</Li>
          <Li k="Projection">cesium-native computes the texture coordinates per tile, in the overlay's tiling scheme.</Li>
          <Li k="Live">tick an overlay or change its opacity while streaming. Several stack in order.</Li>
          <Li k="Point clouds too">each point takes the colour of the map under it.</Li>
        </Bullets>
      }
      right={<Shot src={overlays} width={820} height={461} position="50% 0%" caption="OpenStreetMap draped on Google Photorealistic 3D Tiles over the Colosseum" />}
    />
  </Frame>
);

const P24bEntry: Page = () => (
  <Frame eyebrow="One entry of the list" title="What a tileset can be, and what you can do to it">
    <TwoCol
      leftWidth={1180}
      left={
        <>
          <div style={{ display: 'flex', gap: 14, marginBottom: 26 }}>
            {[
              ['3D Tiles', 'a tileset.json: meshes, points, splats, voxels'],
              ['Cesium ion', 'an asset id and a token'],
              ['Terrain', 'quantized-mesh: a layer.json'],
              ['WGS84 globe', 'the bare ellipsoid, for imagery'],
              ['Aggregate', 'a tileset of tilesets from a 3dtiled server'],
            ].map(([k, v]) => (
              <div key={k} style={{ flex: 1, background: ink.panel, borderRadius: 10, padding: '14px 16px' }}>
                <div style={{ fontSize: 22, fontWeight: 500 }}>{k}</div>
                <div style={{ fontSize: 17, color: ink.muted, lineHeight: 1.3, marginTop: 4 }}>{v}</div>
              </div>
            ))}
          </div>
          <Bullets size={24}>
            <Li k="Raster overlays">imagery draped on it: OpenStreetMap, Esri, IGN, Bing, Google, any URL template, WMTS or WMS.</Li>
            <Li k="Markers">in a tileset of tilesets, an Empty and a white dot per dataset: click one to select it.</Li>
            <Li k="Clipping">cut it with Blender objects: polygons seen from above, or 3D boxes.</Li>
            <Li k="Color correction">gamma and gain per channel, exposure, saturation, contrast, or matched to another tileset.</Li>
            <Li k="Terrain blending">a background goes transparent under it and its border fades into the ground. Beta.</Li>
            <Li k="Match Height to Terrain">one button moves it up or down onto the terrain under it.</Li>
          </Bullets>
        </>
      }
      right={<Shot src={entryBoxes} width={452} height={660} position="50% 58%" caption="Each box has a checkbox and folds" />}
    />
  </Frame>
);

const P24cSetIn: Page = () => (
  <Frame eyebrow="A dataset in its terrain" title="Three clicks from floating and grey to set in the ground">
    <div style={{ display: 'flex', gap: 24 }}>
      <Shot src={matchBefore} width={544} height={360} caption="As loaded: a photogrammetry mesh of Giza, 25 m under Google's ground and darker" />
      <Shot src={matchAfter} width={544} height={360} caption="Match Height to Terrain, then Match Colors onto Google" />
      <Shot src={blendGiza} width={544} height={360} position="0% 0%" caption="Terrain blending: Google is transparent under the mesh, and the border fades over 20 m" />
    </div>
    <div style={{ marginTop: 20 }}>
      <Bullets size={23}>
        <Li k="Match Height to Terrain">compares the lowest heights of both over the ground they share, and moves the tileset's Empty by the median: +25 m here.</Li>
        <Li k="Match Colors">reads both from above where they overlap, 7,242 ground cells here, and fits a gain and a gamma per channel.</Li>
        <Li k="Terrain blending">a coverage raster of the dataset's tiles, read by the terrain's material. Any globe, terrain layer, Google or Bing 3D Tiles is the background.</Li>
      </Bullets>
    </div>
  </Frame>
);

const P24dAggregate: Page = () => (
  <Frame eyebrow="A tileset of tilesets" title="Every dataset of a server, as one entry with a dot each">
    <TwoCol
      leftWidth={720}
      left={
        <Bullets size={25}>
          <Li k="One entry">a set served by a 3dtiled server, or your own manifest of links, as one tileset.json whose leaves are datasets.</Li>
          <Li k="An Empty per dataset">named after it, its tiles parented to it: move one dataset, or hide it and it stops streaming.</Li>
          <Li k="A dot per dataset">a fixed size on screen, faint behind tiles, gone behind the globe. Click it to select the Empty.</Li>
          <Li k="Fly to it">Globe Navigation zooms from the planet to a site; numpad period frames the selected dataset at real size.</Li>
          <Li k="Mixed content">meshes, LiDAR point clouds and splats in the same set, converted to 3D Tiles by the server on the way.</Li>
        </Bullets>
      }
      right={<Shot src={markersGlobe} width={912} height={604} caption="470 open datasets up to 20 km wide, over a globe with imagery, from 7,500 km" />}
    />
  </Frame>
);

const P25Metadata: Page = () => (
  <Frame eyebrow="Feature metadata" title="Colour by class or by number">
    <div style={{ display: 'flex', gap: 40 }}>
      <Shot src={classes} width={820} height={519} caption="swissBUILDINGS3D over Bern by building type, one editable colour per class" />
      <Shot src={ramp} width={820} height={519} caption="The same tiles by building height, through a colour ramp" />
    </div>
    <div style={{ marginTop: 22 }}>
      <Bullets size={25}>
        <Li k="Read from">feature tables, per-point attributes, property textures and tileset metadata.</Li>
        <Li k="Saved">columns, class codes and ranges are rebuilt when the .blend is reopened.</Li>
      </Bullets>
    </div>
  </Frame>
);

const P26Voxels: Page = () => (
  <Frame eyebrow="Voxels" title="Voxel tilesets as blocks, volumes, or colours">
    <Shot src={voxels} width={1680} height={319} caption="Voxel tilesets in Blender: blocks on top, OpenVDB volumes underneath" />
    <div style={{ display: 'flex', gap: 28, marginTop: 40 }}>
      <Card title="Blocks">the cell faces next to empty space, as a mesh. Crisp and opaque, best for classes.</Card>
      <Card title="Volume" accent={ink.violet}>one OpenVDB volume per tile, see-through, for continuous fields.</Card>
      <Card title="Colour other tilesets" accent={ink.mint}>a scan reads the class of the voxel under each pixel.</Card>
      <Card title="Beta: phases" accent={ink.amber}>building phases as volumes, voxelized into a class grid with a year slider.</Card>
    </div>
  </Frame>
);

const P27Tested: Page = () => (
  <Frame eyebrow="Tested on" title="From a basilica interior to the whole globe">
    <div style={{ display: 'flex', gap: 24 }}>
      <Card title="Gaussian splats">basilica interiors scanned as splats, converted to 3D Tiles; the Cesium splat samples.</Card>
      <Card title="Photorealistic 3D Tiles" accent={ink.violet}>Google's tiles over Rome, Paris, Tokyo and the Grand Canyon, through the Map Tiles API.</Card>
      <Card title="Terrain" accent={ink.mint}>quantized-mesh terrain and a bare WGS84 globe, with imagery draped on them.</Card>
    </div>
    <div style={{ display: 'flex', gap: 24, marginTop: 24 }}>
      <Card title="Point clouds" accent={ink.amber}>LiDAR as pnts and COPC tiles, with intensity and classification.</Card>
      <Card title="City models">swissBUILDINGS3D with its metadata; photogrammetry from drones and RealityCapture.</Card>
      <Card title="Voxels" accent={ink.violet}>GeoTOP, the Dutch geological model, and the Cesium voxel samples.</Card>
    </div>
    <div style={{ marginTop: 36 }}>
      <Bullets size={24}>
        <Li k="Blender">4.2 or newer, on Windows, Linux and macOS; splats need 5.3.</Li>
      </Bullets>
    </div>
  </Frame>
);

const P28Install: Page = () => (
  <Frame eyebrow="Install" title="An extension zip, then one button">
    <TwoCol
      leftWidth={860}
      left={
        <Bullets>
          <Li k="1.">
            Download ogc_3dtiles_streaming-&lt;version&gt;.zip from <A href={`${REPO}/releases`} />
          </Li>
          <Li k="2.">Preferences, Get Extensions, Install from Disk.</Li>
          <Li k="3.">In the add-on preferences, Install wheel from GitHub Release, then restart.</Li>
          <Li k="4.">Open the sidebar (N), the 3D Tiles tab: add an entry, paste a URL, press Start.</Li>
        </Bullets>
      }
      right={
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <Card title="No compiler">the wheel matching your Blender and system: Linux x86_64, Windows x64, macOS arm64.</Card>
          <Card title="Without the wheel" accent={ink.violet}>the pure Python backend streams mesh tilesets.</Card>
          <div>
            <div style={{ fontSize: 21, fontWeight: 500, marginBottom: 10 }}>Install from a terminal</div>
            <Code size={20}>{`blender --command extension install-file \\
  -r user_default -e ogc_3dtiles_streaming-<version>.zip`}</Code>
          </div>
        </div>
      }
    />
  </Frame>
);

const P29Close: Page = () => (
  <div style={fill}>
    <Mark />
    <Eyebrow>OGC 3D Tiles Streaming</Eyebrow>
    <h1 style={{ position: 'absolute', left: PAD_X, top: 220, margin: 0, fontFamily: font.display, fontSize: 112, fontWeight: 500, letterSpacing: '-0.04em', lineHeight: 1 }}>
      Paste a tileset URL.
      <br />
      <span style={{ color: 'var(--osd-accent)' }}>Press Start.</span>
    </h1>
    <div style={{ position: 'absolute', left: PAD_X, right: PAD_X, top: 580, borderBottom: `1px solid ${ink.rule}` }}>
      <CloseLine n={1}><A href={REPO} /> · source, issues and pull requests</CloseLine>
      <CloseLine n={2}><A href={`${REPO}/releases`} /> · the extension zip, and these slides as PDF</CloseLine>
      <CloseLine n={3}><A href={SITE} /> · the documentation and the live slides</CloseLine>
      <CloseLine n={4}>Blender 4.2 or newer · splats need 5.3 · MIT licence</CloseLine>
    </div>
    <Footer />
  </div>
);

export const notes: (string | undefined)[] = [
  `A Blender extension that streams OGC 3D Tiles. The engine is cesium-native, the one behind Cesium for Unreal and Unity.`,
  `Blender users cannot open a city. The 3D Tiles crowd cannot path-trace or composite a tileset. This is the bridge between the two.`,
  `Each tick the viewport becomes a cesium-native view state. Selection, loading and unloading are cesium-native's; the add-on turns the result into Blender objects.`,
  `Tiles are ordinary objects under one root Empty per tileset. One colour per tile shows them: each is its own object.`,
  `Everything cesium-native reads: meshes, point clouds, splats, voxels, from a URL, a local file, ion or Google.`,
  `One sidebar tab. Add an entry, paste a URL, press Start.`,
  `Max SSE is how fine: halving it brings the next level of detail. Stream for says which view decides.`,
  `Tile bounds, the latest addition, and colour by tile level: two ways to see what the level of detail does.`,
  `The scene origin anchors Blender's local frame on the globe, in double precision: by place search, or typed in. Paris, Tokyo, Rome and the Grand Canyon here.`,
  `The shared shader, first: the photo as captured, or clay under real lights.`,
  `Then relit by the scene's own lamps, or X-ray to read an interior through its walls.`,
  `All of it is one node group in every tile material. Edit it once.`,
  `Clipping with Blender objects, live. Here a box keeps a block of Google's tiles around the Colosseum.`,
  `The cut happens in three places: selection, geometry, shader.`,
  `Point clouds through a shared Geometry Nodes group. The height reveal demo shows what one shared graph does to every tile.`,
  `The point display group, and the colour sources.`,
  `Splat tilesets as native Blender 5.3 splats, with their level of detail.`,
  `LiDAR classes read from the tiles, in the usual colours, with eye-dome lighting.`,
  `The compositor tree, the atmosphere preset, and Cycles.`,
  `Every kind of camera selects tiles: perspective, orthographic exactly, panoramic as six cube views.`,
  `From above, one colour per tile: the wedge of a perspective camera, the strip of an orthographic one, the disc around a panorama.`,
  `Blender cannot pause a render to wait for tiles. The converged animation steps through the frames itself and renders each one once its tiles are in.`,
  `Files: local and NAS tilesets, libraries, copy into project, exports.`,
  `Raster overlays the way Cesium for Unreal does them, with presets that need no key.`,
  `Everything about one entry: the five types, then the six things its boxes do.`,
  `Giza: as loaded, after the two Match buttons, and with terrain blending. Numbers are from this scene.`,
  `A whole server as one entry. The dots are Empties you can select, hide or fly to.`,
  `Metadata as colours: classes with a palette, numbers with a ramp.`,
  `Voxels as blocks, volumes, or as colours on other tilesets. Phases, in beta, build on the same voxel grid.`,
  `What it was tested on, kept generic.`,
  `Install the zip, then the wheel from the preferences.`,
  `Source, releases and docs at the addresses on screen.`,
];

export const meta: SlideMeta = {
  title: '3D Tiles, streamed into Blender',
  createdAt: '2026-11-05T12:00:00.000Z',
};

export default [
  P01Cover,
  P02Why,
  P03How,
  P04Objects,
  P05Content,
  P06Sidebar,
  P07Lod,
  P08SeeLod,
  P09Origin,
  P10Shader,
  P11Relight,
  P12Graphs,
  P13Clipping,
  P14ClipNodes,
  P15Points,
  P16PointNodes,
  P17Splats,
  P18Beauty,
  P19Render,
  P20Cameras,
  P21Frustums,
  P22Converged,
  P23Files,
  P24Overlays,
  P24bEntry,
  P24cSetIn,
  P24dAggregate,
  P25Metadata,
  P26Voxels,
  P27Tested,
  P28Install,
  P29Close,
] satisfies Page[];
