import type { MeshStandardMaterial } from 'three';
import { workstations } from '../scene/officeLayout';
import type { AgentRole, RoleMarker } from './AgentRole';

export interface AgentDefinition {
  id: string;
  displayName: string;
  role: AgentRole;
  workstationId: AgentRole;
  workstation: string;
  position: readonly [number, number, number];
  rotation: number;
  accent: MeshStandardMaterial;
  marker: RoleMarker;
}

const markers: Record<AgentRole, RoleMarker> = {
  supervisor: 'diamond',
  frontend: 'window',
  backend: 'bars',
  documentation: 'page',
  reviewer: 'check',
};

// Presentation-only configuration. Positions follow the office layout.
export const agents: readonly AgentDefinition[] = workstations.map(
  (station) => ({
    id: `agent-${station.id}`,
    displayName: station.name,
    role: station.id,
    workstationId: station.id,
    workstation: `${station.name} workstation`,
    position: [station.position[0] + 1.15, 0, station.position[2] + 0.7],
    rotation: 0,
    accent: station.accent,
    marker: markers[station.id],
  }),
);

export function getAgentById(id: string | null): AgentDefinition | undefined {
  return agents.find((agent) => agent.id === id);
}
