import { Box } from '../scene/Primitives';
import { materials } from '../scene/materials';
import type { AgentDefinition } from './AgentRegistry';
import { RoleBadge } from './RoleBadge';
import {
  headGeometry,
  selectionRingGeometry,
  uniformMaterial,
} from './agentGeometry';

interface AgentAvatarProps {
  agent: AgentDefinition;
  selected: boolean;
  onSelect: (id: string) => void;
}

export function AgentAvatar({ agent, selected, onSelect }: AgentAvatarProps) {
  return (
    <group
      name={`${agent.displayName} agent`}
      position={[...agent.position]}
      rotation={[0, agent.rotation, 0]}
      onClick={(event) => {
        event.stopPropagation();
        onSelect(agent.id);
      }}
    >
      {selected && (
        <mesh
          position={[0, 0.035, 0]}
          rotation={[-Math.PI / 2, 0, 0]}
          geometry={selectionRingGeometry}
          material={agent.accent}
          dispose={null}
        />
      )}
      <Box
        position={[0, 0.12, 0]}
        scale={[0.31, 0.07, 0.22]}
        material={materials.frame}
      />
      <Box
        position={[-0.105, 0.34, 0]}
        scale={[0.09, 0.42, 0.12]}
        material={uniformMaterial}
      />
      <Box
        position={[0.105, 0.34, 0]}
        scale={[0.09, 0.42, 0.12]}
        material={uniformMaterial}
      />
      <Box
        position={[0, 0.83, 0]}
        scale={[0.39, 0.48, 0.21]}
        material={uniformMaterial}
      />
      <Box
        position={[0, 1.1, 0]}
        scale={[0.43, 0.065, 0.23]}
        material={agent.accent}
      />
      <Box
        position={[-0.26, 0.78, 0]}
        rotation={[0, 0, 0.12]}
        scale={[0.09, 0.38, 0.12]}
        material={uniformMaterial}
      />
      <Box
        position={[0.26, 0.78, 0]}
        rotation={[0, 0, -0.12]}
        scale={[0.09, 0.38, 0.12]}
        material={uniformMaterial}
      />
      <mesh
        position={[0, 1.35, 0]}
        scale={[0.18, 0.2, 0.17]}
        geometry={headGeometry}
        material={materials.paper}
        dispose={null}
      />
      <RoleBadge marker={agent.marker} accent={agent.accent} />
    </group>
  );
}
