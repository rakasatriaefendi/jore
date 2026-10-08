import { act, type ReactNode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ErrorBoundary } from '../../src/app/ErrorBoundary';

function BrokenChild(): ReactNode {
  throw new Error('Simulated renderer initialization failure');
}

describe('ErrorBoundary', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
    container = document.createElement('div');
    document.body.append(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(() => root.unmount());
    container.remove();
    vi.unstubAllGlobals();
  });

  it('renders healthy children', async () => {
    await act(() =>
      root.render(
        <ErrorBoundary>
          <p>Scene ready</p>
        </ErrorBoundary>,
      ),
    );
    expect(container.textContent).toBe('Scene ready');
    expect(container.querySelector('[role="alert"]')).toBeNull();
  });

  it('replaces a failed child with a controlled fallback and recovery action', async () => {
    const diagnostic = vi.spyOn(console, 'error').mockImplementation(() => {});

    await act(() =>
      root.render(
        <ErrorBoundary>
          <BrokenChild />
        </ErrorBoundary>,
      ),
    );

    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      'JORE Visualizer unavailable',
    );
    expect(container.querySelector('button')?.textContent).toBe(
      'Reload visualizer',
    );
    expect(container.textContent).not.toContain(
      'Simulated renderer initialization failure',
    );
    expect(diagnostic).toHaveBeenCalled();
  });
});
