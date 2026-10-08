import type { AgentDefinition } from '../agents/AgentRegistry';
import { visualStatePresentation } from '../agents/visualStatePresentation';
import { useAgentStore } from '../state/useAgentStore';

interface SelectedAgentPanelProps {
  agent: AgentDefinition;
  onClear: () => void;
}

export function SelectedAgentPanel({
  agent,
  onClear,
}: SelectedAgentPanelProps) {
  const visualState = useAgentStore(
    (state) => state.visualStatesById[agent.id],
  );
  return (
    <section className="selected-agent-panel" aria-label="Selected agent">
      <div className="selected-agent-heading">
        <h2>{agent.displayName}</h2>
        <button
          type="button"
          onClick={onClear}
          aria-label="Clear agent selection"
        >
          ×
        </button>
      </div>
      <dl>
        <dt>Role</dt>
        <dd>{agent.displayName}</dd>
        <dt>Workstation</dt>
        <dd>{agent.workstation}</dd>
        <dt>Visual state</dt>
        <dd>{visualStatePresentation[visualState ?? 'idle'].label}</dd>
      </dl>
    </section>
  );
}
