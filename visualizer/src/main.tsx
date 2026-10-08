import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { ErrorBoundary } from './app/ErrorBoundary';
import './app/styles.css';

const root = document.getElementById('root');

if (!root) {
  throw new Error('JORE Visualizer root element is missing.');
}

createRoot(root).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
