import { useState } from 'react';
import { agents } from '../agents/AgentRegistry';
import { agentVisualStates } from '../agents/AgentVisualState';
import { visualStatePresentation } from '../agents/visualStatePresentation';
import { dispatchMockAgentAction } from './mockAgentEvents';

export function MockEventPanel() {
  const [agentId, setAgentId] = useState(agents[0]?.id ?? '');
  const [visualState, setVisualState] = useState(agentVisualStates[0]);

  return (
    <section className="mock-event-panel" aria-label="Mock visual events">
      <h2>Mock visual events</h2>
      <label>
        Agent
        <select
          value={agentId}
          onChange={(event) => setAgentId(event.target.value)}
        >
          {agents.map((agent) => (
            <option key={agent.id} value={agent.id}>
              {agent.displayName}
            </option>
          ))}
        </select>
      </label>
      <label>
        State
        <select
          value={visualState}
          onChange={(event) =>
            setVisualState(event.target.value as typeof visualState)
          }
        >
          {agentVisualStates.map((state) => (
            <option key={state} value={state}>
              {visualStatePresentation[state].label}
            </option>
          ))}
        </select>
      </label>
      <div className="mock-event-actions">
        <button
          type="button"
          onClick={() =>
            dispatchMockAgentAction({
              kind: 'set',
              agentId,
              state: visualState,
            })
          }
        >
          Apply
        </button>
        <button
          type="button"
          onClick={() =>
            dispatchMockAgentAction({ kind: 'reset-agent', agentId })
          }
        >
          Reset agent
        </button>
        <button
          type="button"
          onClick={() => dispatchMockAgentAction({ kind: 'reset-all' })}
        >
          Reset all
        </button>
      </div>
    </section>
  );
}
