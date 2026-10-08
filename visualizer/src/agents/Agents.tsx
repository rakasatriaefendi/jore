import { agents } from './AgentRegistry';
import { AgentAvatar } from './AgentAvatar';

interface AgentsProps {
  selectedAgentId: string | null;
  onSelectAgent: (id: string) => void;
}

export function Agents({ selectedAgentId, onSelectAgent }: AgentsProps) {
  return agents.map((agent) => (
    <AgentAvatar
      key={agent.id}
      agent={agent}
      selected={selectedAgentId === agent.id}
      onSelect={onSelectAgent}
    />
  ));
}
