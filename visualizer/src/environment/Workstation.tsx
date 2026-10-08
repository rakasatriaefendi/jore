import type { MeshStandardMaterial } from 'three';
import { Box } from '../scene/Primitives';
import { materials } from '../scene/materials';

interface WorkstationProps {
  name: string;
  position: [number, number, number];
  rotation?: number;
  accent: MeshStandardMaterial;
  supervisor?: boolean;
}

export function Workstation({
  name,
  position,
  rotation = 0,
  accent,
  supervisor = false,
}: WorkstationProps) {
  const width = supervisor ? 1.85 : 1.55;

  return (
    <group
      name={name + ' workstation'}
      position={position}
      rotation={[0, rotation, 0]}
    >
      <Box
        position={[0, 0.73, 0]}
        scale={[width, 0.1, 0.82]}
        material={materials.desk}
      />
      {[-1, 1].map((side) => (
        <Box
          key={side}
          position={[side * (width / 2 - 0.12), 0.36, 0]}
          scale={[0.12, 0.72, 0.68]}
          material={materials.frame}
        />
      ))}
      <Box
        position={[0, 0.79, 0.36]}
        scale={[width - 0.16, 0.025, 0.035]}
        material={accent}
      />
      <Box
        position={[0, 1.06, -0.25]}
        scale={[0.1, 0.47, 0.08]}
        material={materials.frame}
      />
      <Box
        position={[0, 1.28, -0.24]}
        scale={[0.67, 0.44, 0.07]}
        material={materials.frame}
      />
      <Box
        position={[0, 1.28, -0.195]}
        scale={[0.59, 0.36, 0.015]}
        material={materials.screen}
      />
      <Box
        position={[0, 0.79, 0.13]}
        scale={[0.72, 0.025, 0.2]}
        material={materials.frame}
      />
      <Box
        position={[0, 0.46, 1.04]}
        scale={[0.6, 0.1, 0.59]}
        material={materials.seat}
      />
      <Box
        position={[0, 0.79, 1.31]}
        scale={[0.6, 0.64, 0.09]}
        material={materials.seat}
      />
      <Box
        position={[0, 0.22, 1.04]}
        scale={[0.07, 0.43, 0.07]}
        material={materials.frame}
      />
      <Box
        position={[0, 0.06, 1.04]}
        scale={[0.54, 0.06, 0.46]}
        material={materials.frame}
      />
    </group>
  );
}
