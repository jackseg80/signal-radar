export default function EmptyState({ message = 'No data available' }) {
  return (
    <div className="text-[--text-muted] text-center py-8 text-sm">
      {message}
    </div>
  );
}
