import { materials } from './materials';
import type { AgentRole } from '../agents/AgentRole';

interface WorkstationLayout {
  id: AgentRole;
  name: string;
  location: string;
  position: readonly [number, number, number];
  accent: typeof materials.pink;
  supervisor: boolean;
}

export const workstations = [
  {
    id: 'supervisor',
    name: 'Supervisor',
    location: 'back center',
    position: [-1.65, 0, -3.55],
    accent: materials.pink,
    supervisor: true,
  },
  {
    id: 'frontend',
    name: 'Frontend',
    location: 'left middle',
    position: [-3.25, 0, -1.0],
    accent: materials.blue,
    supervisor: false,
  },
  {
    id: 'backend',
    name: 'Backend',
    location: 'right middle',
    position: [2.35, 0, -1.0],
    accent: materials.green,
    supervisor: false,
  },
  {
    id: 'documentation',
    name: 'Documentation',
    location: 'left front',
    position: [-3.25, 0, 1.75],
    accent: materials.amber,
    supervisor: false,
  },
  {
    id: 'reviewer',
    name: 'Reviewer',
    location: 'right front',
    position: [2.35, 0, 1.75],
    accent: materials.violet,
    supervisor: false,
  },
] as const satisfies readonly WorkstationLayout[];
