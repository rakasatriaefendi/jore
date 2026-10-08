import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { getAgentById } from '../../src/agents/AgentRegistry';
import { MockEventPanel } from '../../src/debug/MockEventPanel';
import { useAgentStore } from '../../src/state/useAgentStore';
import { SelectedAgentPanel } from '../../src/ui/SelectedAgentPanel';

describe('mock visual events', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    useAgentStore.getState().resetAllAgents();
    container = document.createElement('div');
    document.body.append(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it('applies a mock action and updates the selected-agent panel', () => {
    const reviewer = getAgentById('agent-reviewer');
    if (!reviewer) throw new Error('Missing reviewer');

    act(() => {
      root.render(
        <>
          <MockEventPanel />
          <SelectedAgentPanel agent={reviewer} onClear={() => undefined} />
        </>,
      );
    });
    const [agentSelect, stateSelect] = container.querySelectorAll('select');
    if (!agentSelect || !stateSelect) throw new Error('Missing mock controls');

    act(() => {
      agentSelect.value = reviewer.id;
      agentSelect.dispatchEvent(new Event('change', { bubbles: true }));
      stateSelect.value = 'reviewing';
      stateSelect.dispatchEvent(new Event('change', { bubbles: true }));
    });
    const apply = [...container.querySelectorAll('button')].find(
      (button) => button.textContent === 'Apply',
    );
    if (!apply) throw new Error('Missing Apply button');
    act(() => apply.click());

    expect(useAgentStore.getState().getVisualState(reviewer.id)).toBe(
      'reviewing',
    );
    expect(
      container.querySelector('.selected-agent-panel')?.textContent,
    ).toContain('Visual stateReviewing');
  });
});
