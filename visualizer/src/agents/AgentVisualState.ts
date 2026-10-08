export const agentVisualStates = [
  'idle',
  'assigned',
  'walking',
  'working',
  'waiting',
  'reviewing',
  'success',
  'error',
] as const;

export type AgentVisualState = (typeof agentVisualStates)[number];
