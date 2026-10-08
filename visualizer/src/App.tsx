import { useState } from 'react';
import { SceneCanvas } from './scene/SceneCanvas';
import { Header } from './ui/Header';
import { OfficeKey } from './ui/OfficeKey';

export function App() {
  const [resetViewKey, setResetViewKey] = useState(0);

  return (
    <div className="app">
      <Header onResetView={() => setResetViewKey((key) => key + 1)} />
      <main className="visualizer-root" aria-label="3D visualizer">
        <SceneCanvas resetViewKey={resetViewKey} />
        <OfficeKey />
      </main>
    </div>
  );
}
