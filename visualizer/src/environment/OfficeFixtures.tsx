import { Box } from '../scene/Primitives';
import { materials } from '../scene/materials';

export function OfficeFixtures() {
  return (
    <group>
      {/* Whiteboard on the back wall. */}
      <Box
        position={[3.35, 1.17, -5.11]}
        scale={[2.7, 1.15, 0.1]}
        material={materials.trim}
      />
      <Box
        position={[3.35, 1.17, -5.04]}
        scale={[2.53, 0.97, 0.02]}
        material={materials.board}
      />
      <Box
        position={[3.35, 0.55, -4.98]}
        scale={[1.4, 0.05, 0.16]}
        material={materials.frame}
      />

      {/* Low storage stays visible behind the foreground desks. */}
      <Box
        position={[-4.9, 0.62, 3.65]}
        scale={[0.92, 1.24, 0.78]}
        material={materials.frame}
      />
      <Box
        position={[-4.9, 1.26, 3.65]}
        scale={[1.04, 0.08, 0.9]}
        material={materials.desk}
      />
      <Box
        position={[-4.9, 0.76, 4.06]}
        scale={[0.7, 0.025, 0.025]}
        material={materials.trim}
      />
      <Box
        position={[-4.9, 0.34, 4.06]}
        scale={[0.7, 0.025, 0.025]}
        material={materials.trim}
      />

      <Box
        position={[-3.35, 0.65, 4.15]}
        scale={[1.15, 0.08, 0.48]}
        material={materials.desk}
      />
      <Box
        position={[-3.82, 0.32, 4.15]}
        scale={[0.08, 0.65, 0.48]}
        material={materials.frame}
      />
      <Box
        position={[-2.88, 0.32, 4.15]}
        scale={[0.08, 0.65, 0.48]}
        material={materials.frame}
      />
      <Box
        position={[-3.4, 0.76, 4.15]}
        scale={[0.5, 0.12, 0.34]}
        material={materials.paper}
      />

      <Box
        position={[4.8, 0.32, 4.0]}
        scale={[0.92, 0.64, 0.86]}
        material={materials.desk}
      />
      <Box
        position={[4.8, 0.69, 4.0]}
        scale={[0.76, 0.07, 0.7]}
        material={materials.paper}
      />
    </group>
  );
}
