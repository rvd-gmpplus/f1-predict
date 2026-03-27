import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center px-4 text-center">
      <div className="text-8xl font-mono font-bold text-f1-red mb-4">404</div>
      <h1 className="text-2xl font-bold mb-2">Page Not Found</h1>
      <p className="text-f1-muted mb-8 max-w-md">
        Looks like this page retired from the race. Let&apos;s get you back on track.
      </p>
      <Link href="/dashboard" className="btn-primary">
        Back to Dashboard
      </Link>
    </div>
  );
}
