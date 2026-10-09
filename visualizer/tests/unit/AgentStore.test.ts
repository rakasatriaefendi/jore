import { beforeEach, describe, expect, it, vi } from 'vitest';
import { agents } from '../../src/agents/AgentRegistry';
import { useAgentStore } from '../../src/state/useAgentStore';

const supervisor = 'agent-supervisor';
const reviewer = 'agent-reviewer';

describe('agent visual-state store', () => {
  it('initializes every registered agent to idle in a fresh store', async () => {
    vi.resetModules();
    const { useAgentStore: freshStore } =
      await import('../../src/state/useAgentStore');
    expect(agents).toHaveLength(5);
    for (const agent of agents) {
      expect(freshStore.getState().getVisualState(agent.id)).toBe('idle');
    }
  });

  describe('transitions and resets', () => {
    beforeEach(() => useAgentStore.getState().resetAllAgents());

    it('supports independent working, waiting, reviewing, success, and error transitions', () => {
      const store = useAgentStore.getState();
      store.setVisualState(supervisor, 'working');
      expect(store.getVisualState(supervisor)).toBe('working');
      store.setVisualState(supervisor, 'waiting');
      expect(store.getVisualState(supervisor)).toBe('waiting');
      store.setVisualState(reviewer, 'reviewing');
      expect(store.getVisualState(reviewer)).toBe('reviewing');
      store.setVisualState(supervisor, 'success');
      expect(store.getVisualState(supervisor)).toBe('success');
      store.setVisualState(reviewer, 'error');
      expect(store.getVisualState(reviewer)).toBe('error');
      expect(store.getVisualState('agent-backend')).toBe('idle');
    });

    it('resets one agent without changing another', () => {
      const store = useAgentStore.getState();
      store.setVisualState(supervisor, 'working');
      store.setVisualState(reviewer, 'reviewing');
      store.resetAgent(supervisor);
      expect(store.getVisualState(supervisor)).toBe('idle');
      expect(store.getVisualState(reviewer)).toBe('reviewing');
    });

    it('resets all agents and ignores unknown ids', () => {
      const store = useAgentStore.getState();
      store.setVisualState(supervisor, 'success');
      store.setVisualState(reviewer, 'error');
      store.setVisualState('unknown', 'working');
      expect(store.getVisualState('unknown')).toBeUndefined();
      store.resetAllAgents();
      for (const agent of agents) {
        expect(store.getVisualState(agent.id)).toBe('idle');
      }
    });
  });
});
