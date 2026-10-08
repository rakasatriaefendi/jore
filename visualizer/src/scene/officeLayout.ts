import { materials } from './materials';

export const workstations = [
  {
    name: 'Supervisor',
    location: 'back center',
    position: [-1.65, 0, -3.55],
    accent: materials.pink,
    supervisor: true,
  },
  {
    name: 'Frontend',
    location: 'left middle',
    position: [-3.25, 0, -1.0],
    accent: materials.blue,
    supervisor: false,
  },
  {
    name: 'Backend',
    location: 'right middle',
    position: [2.35, 0, -1.0],
    accent: materials.green,
    supervisor: false,
  },
  {
    name: 'Documentation',
    location: 'left front',
    position: [-3.25, 0, 1.75],
    accent: materials.amber,
    supervisor: false,
  },
  {
    name: 'Reviewer',
    location: 'right front',
    position: [2.35, 0, 1.75],
    accent: materials.violet,
    supervisor: false,
  },
] as const;
