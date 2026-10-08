import type { AgentDefinition } from './AgentRegistry';
import type { ProjectedAgentLabel } from './AgentLabelProjection';

interface AgentLabelProps {
  agent: AgentDefinition;
  position: ProjectedAgentLabel | undefined;
  selected: boolean;
  onSelect: (id: string) => void;
}

export function AgentLabel({
  agent,
  position,
  selected,
  onSelect,
}: AgentLabelProps) {
  if (!position?.visible) return null;

  return (
    <button
      className="agent-label"
      type="button"
      style={{ left: position.x, top: position.y }}
      aria-label={`Select ${agent.displayName}`}
      aria-pressed={selected}
      data-testid={`agent-label-${agent.role}`}
      onClick={() => onSelect(agent.id)}
    >
      {agent.displayName}
    </button>
  );
}
