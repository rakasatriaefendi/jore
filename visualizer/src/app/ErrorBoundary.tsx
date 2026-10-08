import { Component, type ErrorInfo, type ReactNode } from 'react';
import { FatalError } from '../ui/FatalError';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    if (import.meta.env.DEV) {
      console.error(
        'JORE Visualizer failed to initialize.',
        error,
        info.componentStack,
      );
    }
  }

  render() {
    return this.state.hasError ? <FatalError /> : this.props.children;
  }
}
