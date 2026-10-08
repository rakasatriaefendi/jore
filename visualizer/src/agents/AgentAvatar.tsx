import { Box } from '../scene/Primitives';
import { materials } from '../scene/materials';
import { useAgentStore } from '../state/useAgentStore';
import type { AgentDefinition } from './AgentRegistry';
import { RoleBadge } from './RoleBadge';
import {
  headGeometry,
  selectionRingGeometry,
  uniformMaterial,
} from './agentGeometry';
import { visualStatePresentation } from './visualStatePresentation';

interface AgentAvatarProps {
  agent: AgentDefinition;
  selected: boolean;
  onSelect: (id: string) => void;
}

export function AgentAvatar({ agent, selected, onSelect }: AgentAvatarProps) {
  const visualState = useAgentStore(
    (state) => state.visualStatesById[agent.id],
  );
  const pose = visualStatePresentation[visualState ?? 'idle'].pose;
  return (
    <group
      name={`${agent.displayName} agent`}
      position={[...agent.position]}
      rotation={[0, agent.rotation + pose.turn, 0]}
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
      <group position={[0, pose.lift, 0]}>
        <Box
          position={[-0.105, 0.34, 0]}
          rotation={[0, 0, pose.leftLeg]}
          scale={[0.09, 0.42, 0.12]}
          material={uniformMaterial}
        />
        <Box
          position={[0.105, 0.34, 0]}
          rotation={[0, 0, pose.rightLeg]}
          scale={[0.09, 0.42, 0.12]}
          material={uniformMaterial}
        />
        <group rotation={[pose.lean, 0, 0]} position={[0, 0.7, 0]}>
          <Box
            position={[0, 0.13, 0]}
            scale={[0.39, 0.48, 0.21]}
            material={uniformMaterial}
          />
          <Box
            position={[0, 0.4, 0]}
            scale={[0.43, 0.065, 0.23]}
            material={agent.accent}
          />
          <Box
            position={[-0.26, 0.08, 0]}
            rotation={[0, 0, pose.leftArm]}
            scale={[0.09, 0.38, 0.12]}
            material={uniformMaterial}
          />
          <Box
            position={[0.26, 0.08, 0]}
            rotation={[0, 0, pose.rightArm]}
            scale={[0.09, 0.38, 0.12]}
            material={uniformMaterial}
          />
          <mesh
            position={[0, 0.65, 0]}
            rotation={[pose.headTilt, 0, 0]}
            scale={[0.18, 0.2, 0.17]}
            geometry={headGeometry}
            material={materials.paper}
            dispose={null}
          />
          <group position={[0, -0.7, 0]}>
            <RoleBadge marker={agent.marker} accent={agent.accent} />
          </group>
        </group>
      </group>
    </group>
  );
}
