import Link from "next/link";

export default function LandingPage() {
  return (
    <div className="relative min-h-[calc(100vh-4rem)] flex items-center justify-center overflow-hidden">
      {/* Video background */}
      <video
        autoPlay
        muted
        loop
        playsInline
        className="absolute inset-0 w-full h-full object-cover opacity-30"
      >
        <source src="/videos/hero-pitstop.mp4" type="video/mp4" />
      </video>

      {/* Gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-b from-f1-surface/80 via-f1-surface/60 to-f1-surface" />

      {/* Content */}
      <div className="relative z-10 text-center px-4 max-w-3xl mx-auto animate-fade-in">
        <div className="inline-flex items-center gap-2 bg-f1-red/10 border border-f1-red/30 rounded-full px-4 py-1.5 text-sm text-f1-red font-medium mb-8">
          <span className="w-2 h-2 bg-f1-red rounded-full animate-pulse" />
          2026 Season Live
        </div>

        <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold mb-6 leading-tight">
          Predict the Race.
          <br />
          <span className="text-gradient-red">Beat the AI.</span>
        </h1>

        <p className="text-xl text-gray-400 mb-10 max-w-xl mx-auto leading-relaxed">
          Submit your qualifying and race predictions for every F1 weekend.
          Compete against an evolving AI model and climb the season leaderboard.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link href="/auth/register" className="btn-primary text-lg px-8 py-3">
            Get Started
          </Link>
          <Link href="/leaderboard" className="btn-secondary text-lg px-8 py-3">
            View Leaderboard
          </Link>
        </div>

        {/* Stats bar */}
        <div className="mt-16 grid grid-cols-3 gap-8 max-w-md mx-auto">
          <div>
            <div className="text-2xl font-bold text-white">10</div>
            <div className="text-sm text-f1-muted">Categories</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-white">24</div>
            <div className="text-sm text-f1-muted">Races</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-f1-red">537</div>
            <div className="text-sm text-f1-muted">Max Points</div>
          </div>
        </div>
      </div>
    </div>
  );
}
