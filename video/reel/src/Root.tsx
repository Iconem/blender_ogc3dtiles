import { Composition } from "remotion"
import { BlenderDemo, blenderDemoDuration } from "./BlenderDemo"
import { FPS } from "./Demo3"

export const Root: React.FC = () => (
  <>
    <Composition id="BlenderDemo" component={BlenderDemo} width={1920} height={1080} fps={FPS} durationInFrames={blenderDemoDuration()} />
  </>
)
