import type { AgentDefinition } from '../agents/AgentRegistry';

interface SelectedAgentPanelProps {
  agent: AgentDefinition;
  onClear: () => void;
}

export function SelectedAgentPanel({
  agent,
  onClear,
}: SelectedAgentPanelProps) {
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
      </dl>
    </section>
  );
}
