import { Box } from '../scene/Primitives';
import { materials } from '../scene/materials';

export function OfficeRoom() {
  return (
    <group>
      <Box
        position={[0, -0.16, 0]}
        scale={[12.6, 0.32, 10.6]}
        material={materials.floor}
      />
      <Box
        position={[0, 1.05, -5.25]}
        scale={[12.6, 2.1, 0.18]}
        material={materials.wall}
      />
      <Box
        position={[-6.2, 0.85, 0]}
        scale={[0.18, 1.7, 10.6]}
        material={materials.wall}
      />
      <Box
        position={[6.2, 0.3, 0]}
        scale={[0.18, 0.6, 10.6]}
        material={materials.wall}
      />
      <Box
        position={[-4.35, 0.3, 5.2]}
        scale={[3.9, 0.6, 0.18]}
        material={materials.wall}
      />
      <Box
        position={[4.35, 0.3, 5.2]}
        scale={[3.9, 0.6, 0.18]}
        material={materials.wall}
      />
      <Box
        position={[-2.4, 0.03, 5.19]}
        scale={[0.15, 0.06, 0.5]}
        material={materials.pink}
      />
      <Box
        position={[2.4, 0.03, 5.19]}
        scale={[0.15, 0.06, 0.5]}
        material={materials.pink}
      />
    </group>
  );
}
