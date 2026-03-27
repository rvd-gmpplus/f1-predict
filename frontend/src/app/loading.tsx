export default function Loading() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="w-10 h-10 border-2 border-f1-red border-t-transparent rounded-full animate-spin" />
        <p className="text-f1-muted text-sm">Loading...</p>
      </div>
    </div>
  );
}
