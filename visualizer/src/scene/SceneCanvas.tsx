import { Canvas } from '@react-three/fiber';
import { OfficeCameraControls } from '../camera/OfficeCameraControls';
import { initialCameraPosition } from '../camera/initialCameraPosition';
import { FatalError } from '../ui/FatalError';
import { OfficeScene } from './OfficeScene';

interface SceneCanvasProps {
  resetViewKey: number;
}

export function SceneCanvas({ resetViewKey }: SceneCanvasProps) {
  return (
    <Canvas
      camera={{ position: [...initialCameraPosition], fov: 45 }}
      dpr={[1, 2]}
      frameloop="demand"
      fallback={
        <FatalError message="WebGL is unavailable. Enable browser hardware acceleration or use a WebGL-capable browser." />
      }
      aria-label="3D office prototype. Drag to orbit, scroll to zoom, and right-drag to pan."
    >
      <OfficeScene />
      <OfficeCameraControls resetViewKey={resetViewKey} />
    </Canvas>
  );
}
