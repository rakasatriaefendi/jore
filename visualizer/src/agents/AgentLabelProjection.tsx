import { useThree } from '@react-three/fiber';
import { useEffect } from 'react';
import { Vector3 } from 'three';
import { agents } from './AgentRegistry';

export interface ProjectedAgentLabel {
  x: number;
  y: number;
  visible: boolean;
}

export type AgentLabelPositions = Record<string, ProjectedAgentLabel>;

const labelPoints = agents.map((agent) => ({
  id: agent.id,
  point: new Vector3(
    agent.position[0],
    agent.position[1] + 1.63,
    agent.position[2],
  ),
}));

interface AgentLabelProjectionProps {
  onProject: (positions: AgentLabelPositions) => void;
}

export function AgentLabelProjection({ onProject }: AgentLabelProjectionProps) {
  const camera = useThree((state) => state.camera);
  const controls = useThree((state) => state.controls);
  const width = useThree((state) => state.size.width);
  const height = useThree((state) => state.size.height);

  useEffect(() => {
    let frame = 0;
    const projected = new Vector3();
    // R3F types controls as a generic EventDispatcher; makeDefault installs OrbitControls here.
    const changeControls = controls as unknown as {
      addEventListener: (event: 'change', listener: () => void) => void;
      removeEventListener: (event: 'change', listener: () => void) => void;
    } | null;

    const project = () => {
      frame = 0;
      camera.updateMatrixWorld();
      const positions: AgentLabelPositions = {};
      for (const { id, point } of labelPoints) {
        projected.copy(point).project(camera);
        positions[id] = {
          x: ((projected.x + 1) * width) / 2,
          y: ((1 - projected.y) * height) / 2,
          visible: projected.z >= -1 && projected.z <= 1,
        };
      }
      onProject(positions);
    };

    const schedule = () => {
      if (frame === 0) frame = requestAnimationFrame(project);
    };

    schedule();
    changeControls?.addEventListener('change', schedule);
    return () => {
      changeControls?.removeEventListener('change', schedule);
      cancelAnimationFrame(frame);
    };
  }, [camera, controls, width, height, onProject]);

  return null;
}
