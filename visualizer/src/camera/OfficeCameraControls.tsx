import { OrbitControls } from '@react-three/drei';
import { useThree } from '@react-three/fiber';
import { useEffect, useRef } from 'react';
import { initialCameraPosition } from './initialCameraPosition';

interface OfficeCameraControlsProps {
  resetViewKey: number;
}

export function OfficeCameraControls({
  resetViewKey,
}: OfficeCameraControlsProps) {
  const camera = useThree((state) => state.camera);
  const controls = useRef<React.ComponentRef<typeof OrbitControls>>(null);

  useEffect(() => {
    if (resetViewKey === 0 || !controls.current) return;
    camera.position.set(...initialCameraPosition);
    controls.current.target.set(0, 0, 0);
    controls.current.update();
  }, [camera, resetViewKey]);

  return (
    <OrbitControls
      ref={controls}
      makeDefault
      minDistance={9}
      maxDistance={28}
      minPolarAngle={0.35}
      maxPolarAngle={Math.PI / 2.1}
      enableDamping
    />
  );
}
