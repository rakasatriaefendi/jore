import { useState } from 'react';
import { getAgentById } from './agents/AgentRegistry';
import { AgentLabels } from './agents/AgentLabels';
import type { AgentLabelPositions } from './agents/AgentLabelProjection';
import { MockEventPanel } from './debug/MockEventPanel';
import { SceneCanvas } from './scene/SceneCanvas';
import { Header } from './ui/Header';
import { OfficeKey } from './ui/OfficeKey';
import { SelectedAgentPanel } from './ui/SelectedAgentPanel';

export function App() {
  const [resetViewKey, setResetViewKey] = useState(0);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [labelPositions, setLabelPositions] = useState<AgentLabelPositions>({});
  const selectedAgent = getAgentById(selectedAgentId);

  return (
    <div className="app">
      <Header onResetView={() => setResetViewKey((key) => key + 1)} />
      <main className="visualizer-root" aria-label="3D visualizer">
        <SceneCanvas
          resetViewKey={resetViewKey}
          selectedAgentId={selectedAgentId}
          onSelectAgent={setSelectedAgentId}
          onProjectLabels={setLabelPositions}
        />
        <AgentLabels
          positions={labelPositions}
          selectedAgentId={selectedAgentId}
          onSelectAgent={setSelectedAgentId}
        />
        <OfficeKey />
        {import.meta.env.DEV && <MockEventPanel />}
        {selectedAgent && (
          <SelectedAgentPanel
            agent={selectedAgent}
            onClear={() => setSelectedAgentId(null)}
          />
        )}
      </main>
    </div>
  );
}
