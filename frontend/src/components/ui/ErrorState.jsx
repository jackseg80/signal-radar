export default function ErrorState({ message, onRetry }) {
  return (
    <div className="bg-red-950/30 border border-red-500/30 rounded-xl p-4 text-red-400 text-sm">
      <p>Failed to load data: {message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-2 text-xs underline hover:text-red-300 cursor-pointer"
        >
          Retry
        </button>
      )}
    </div>
  );
}
