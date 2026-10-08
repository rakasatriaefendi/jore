import type { AgentVisualState } from './AgentVisualState';
import { visualStatePresentation } from './visualStatePresentation';

export function AgentStatusIndicator({ state }: { state: AgentVisualState }) {
  const { label, symbol } = visualStatePresentation[state];
  return (
    <span className="agent-status-indicator" data-visual-state={state}>
      <span aria-hidden="true">{symbol}</span> {label}
    </span>
  );
}
