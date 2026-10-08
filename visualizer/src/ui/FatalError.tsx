interface FatalErrorProps {
  message?: string;
}

export function FatalError({
  message = 'The visualizer could not start. Reload the page to try again.',
}: FatalErrorProps) {
  return (
    <section className="fatal-error" role="alert">
      <h1>JORE Visualizer unavailable</h1>
      <p>{message}</p>
      <button type="button" onClick={() => window.location.reload()}>
        Reload visualizer
      </button>
    </section>
  );
}
