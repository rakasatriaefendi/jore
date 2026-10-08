import { describe, expect, it } from 'vitest';
import { agents, getAgentById } from '../../src/agents/AgentRegistry';
import { workstations } from '../../src/scene/officeLayout';

describe('agent registry', () => {
  it('has one distinct presentation agent for each intended workstation', () => {
    expect(agents).toHaveLength(5);
    expect(new Set(agents.map((agent) => agent.id)).size).toBe(5);
    expect(new Set(agents.map((agent) => agent.role))).toEqual(
      new Set([
        'supervisor',
        'frontend',
        'backend',
        'documentation',
        'reviewer',
      ]),
    );

    for (const agent of agents) {
      const workstation = workstations.find(
        (station) => station.id === agent.workstationId,
      );
      expect(workstation).toBeDefined();
      if (!workstation)
        throw new Error(`Missing workstation for ${agent.role}`);
      expect(workstation.name).toBe(agent.displayName);
      expect(agent.position[0]).toBeCloseTo(workstation.position[0] + 1.15);
      expect(agent.position[2]).toBeCloseTo(workstation.position[2] + 0.7);
      expect(agent.accent).toBe(workstation.accent);
      expect(getAgentById(agent.id)).toBe(agent);
    }
  });

  it('uses distinct badge shapes and does not resolve an unknown selection', () => {
    expect(new Set(agents.map((agent) => agent.marker)).size).toBe(5);
    expect(getAgentById('missing')).toBeUndefined();
    expect(getAgentById(null)).toBeUndefined();
  });
});
