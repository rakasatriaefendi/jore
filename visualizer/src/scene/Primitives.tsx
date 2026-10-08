import type { MeshStandardMaterial } from 'three';
import { cube } from './materials';

type Vec3 = [number, number, number];

interface BoxProps {
  position: Vec3;
  scale: Vec3;
  material: MeshStandardMaterial;
  rotation?: Vec3;
}

export function Box({ position, scale, material, rotation }: BoxProps) {
  return (
    <mesh
      position={position}
      scale={scale}
      rotation={rotation}
      geometry={cube}
      material={material}
      dispose={null}
    />
  );
}
