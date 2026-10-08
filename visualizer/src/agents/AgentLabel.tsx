import type { AgentDefinition } from './AgentRegistry';
import type { ProjectedAgentLabel } from './AgentLabelProjection';
import { AgentStatusIndicator } from './AgentStatusIndicator';
import { useAgentStore } from '../state/useAgentStore';

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
  const visualState = useAgentStore(
    (state) => state.visualStatesById[agent.id],
  );
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
      <span>{agent.displayName}</span>
      <AgentStatusIndicator state={visualState ?? 'idle'} />
    </button>
  );
}
