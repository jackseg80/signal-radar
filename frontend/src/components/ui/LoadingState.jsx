export default function LoadingState({ rows = 3 }) {
  return (
    <div className="space-y-3 animate-pulse">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-4 bg-white/5 rounded w-full" />
      ))}
    </div>
  );
}
