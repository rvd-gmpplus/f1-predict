export function Footer() {
  return (
    <footer className="border-t border-f1-border bg-f1-carbon/50 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-f1-muted">
          <p>
            F1 <span className="text-f1-red">Predict</span> &mdash; Beat the AI, top the leaderboard.
          </p>
          <p>
            Not affiliated with Formula 1 or FIA.
          </p>
        </div>
      </div>
    </footer>
  );
}
