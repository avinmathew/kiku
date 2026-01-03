interface LoadingIndicatorProps {
  message?: string;
  progress?: number;
}

export default function LoadingIndicator({ message, progress }: LoadingIndicatorProps) {
  const progressPercent = progress !== undefined && progress > 0 ? Math.round(progress * 100) : 0;
  
  return (
    <div className="loading-indicator">
      {message && <p className="loading-message">{message}</p>}
      {progress !== undefined && progress > 0 && (
        <div className="progress-section">
          <div className="progress-bar-container">
            <div
              className="progress-bar"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <div className="progress-text">{progressPercent}%</div>
        </div>
      )}
    </div>
  );
}

