import type { AgentVisualState } from '../agents/AgentVisualState';
import { useAgentStore } from '../state/useAgentStore';

// Local development actions only. These are not wire events or a protocol schema.
export type MockAgentAction =
  | { kind: 'set'; agentId: string; state: AgentVisualState }
  | { kind: 'reset-agent'; agentId: string }
  | { kind: 'reset-all' };

export function dispatchMockAgentAction(action: MockAgentAction): void {
  const store = useAgentStore.getState();
  switch (action.kind) {
    case 'set':
      store.setVisualState(action.agentId, action.state);
      break;
    case 'reset-agent':
      store.resetAgent(action.agentId);
      break;
    case 'reset-all':
      store.resetAllAgents();
      break;
  }
}
