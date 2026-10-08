import { create } from 'zustand';
import { agents } from '../agents/AgentRegistry';
import type { AgentVisualState } from '../agents/AgentVisualState';

type AgentVisualStates = Record<string, AgentVisualState>;

function idleStates(): AgentVisualStates {
  return Object.fromEntries(agents.map((agent) => [agent.id, 'idle']));
}

interface AgentStore {
  visualStatesById: AgentVisualStates;
  getVisualState: (id: string) => AgentVisualState | undefined;
  setVisualState: (id: string, visualState: AgentVisualState) => void;
  resetAgent: (id: string) => void;
  resetAllAgents: () => void;
}

export const useAgentStore = create<AgentStore>()((set, get) => ({
  visualStatesById: idleStates(),
  getVisualState: (id) => get().visualStatesById[id],
  setVisualState: (id, visualState) =>
    set((current) => {
      if (
        !Object.hasOwn(current.visualStatesById, id) ||
        current.visualStatesById[id] === visualState
      )
        return current;
      return {
        visualStatesById: { ...current.visualStatesById, [id]: visualState },
      };
    }),
  resetAgent: (id) => get().setVisualState(id, 'idle'),
  resetAllAgents: () => set({ visualStatesById: idleStates() }),
}));
