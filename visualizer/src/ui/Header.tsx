interface HeaderProps {
  onResetView: () => void;
}

export function Header({ onResetView }: HeaderProps) {
  return (
    <header className="app-header">
      <h1>JORE Visualizer</h1>
      <div className="header-actions">
        <p>v1.13 Development</p>
        <button type="button" onClick={onResetView}>
          Reset View
        </button>
      </div>
    </header>
  );
}
