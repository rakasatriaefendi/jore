import { Box } from '../scene/Primitives';
import type { AgentDefinition } from './AgentRegistry';
import { uniformMaterial } from './agentGeometry';

interface RoleBadgeProps {
  marker: AgentDefinition['marker'];
  accent: AgentDefinition['accent'];
}

export function RoleBadge({ marker, accent }: RoleBadgeProps) {
  switch (marker) {
    case 'diamond':
      return (
        <Box
          position={[0, 0.94, 0.12]}
          rotation={[0, 0, Math.PI / 4]}
          scale={[0.12, 0.12, 0.025]}
          material={accent}
        />
      );
    case 'window':
      return (
        <>
          <Box
            position={[0, 0.94, 0.12]}
            scale={[0.16, 0.13, 0.025]}
            material={accent}
          />
          <Box
            position={[0, 0.96, 0.14]}
            scale={[0.1, 0.05, 0.01]}
            material={uniformMaterial}
          />
        </>
      );
    case 'bars':
      return (
        <>
          <Box
            position={[0, 0.98, 0.12]}
            scale={[0.16, 0.04, 0.025]}
            material={accent}
          />
          <Box
            position={[0, 0.9, 0.12]}
            scale={[0.16, 0.04, 0.025]}
            material={accent}
          />
        </>
      );
    case 'page':
      return (
        <>
          <Box
            position={[0, 0.94, 0.12]}
            scale={[0.13, 0.17, 0.025]}
            material={accent}
          />
          <Box
            position={[0, 0.92, 0.14]}
            scale={[0.08, 0.02, 0.01]}
            material={uniformMaterial}
          />
        </>
      );
    case 'check':
      return (
        <>
          <Box
            position={[-0.035, 0.92, 0.12]}
            rotation={[0, 0, -0.7]}
            scale={[0.035, 0.09, 0.025]}
            material={accent}
          />
          <Box
            position={[0.035, 0.95, 0.12]}
            rotation={[0, 0, 0.55]}
            scale={[0.035, 0.16, 0.025]}
            material={accent}
          />
        </>
      );
  }
}
