import { agents } from './AgentRegistry';
import { AgentLabel } from './AgentLabel';
import type { AgentLabelPositions } from './AgentLabelProjection';

interface AgentLabelsProps {
  positions: AgentLabelPositions;
  selectedAgentId: string | null;
  onSelectAgent: (id: string) => void;
}

export function AgentLabels({
  positions,
  selectedAgentId,
  onSelectAgent,
}: AgentLabelsProps) {
  return (
    <div className="agent-label-layer">
      {agents.map((agent) => (
        <AgentLabel
          key={agent.id}
          agent={agent}
          position={positions[agent.id]}
          selected={selectedAgentId === agent.id}
          onSelect={onSelectAgent}
        />
      ))}
    </div>
  );
}
