import { useRef, useEffect, useState } from 'react';

interface AudioPlayerProps {
  audioUrl: string;
  currentTime: number;
  duration: number;
  onTimeUpdate: (time: number) => void;
  onDurationChange: (duration: number) => void;
  onSeek: (time: number) => void;
  filename?: string;
  isStuck?: boolean;
}

export default function AudioPlayer({
  audioUrl,
  currentTime,
  duration,
  onTimeUpdate,
  onDurationChange,
  onSeek,
  filename,
  isStuck = false,
}: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const isSeekingRef = useRef(false);
  const lastExternalTimeRef = useRef(currentTime);

  // Sync audio element with external currentTime
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const handleTimeUpdate = () => {
      if (!isSeekingRef.current) {
        onTimeUpdate(audio.currentTime);
      }
    };

    const handleDurationChange = () => {
      if (audio.duration) {
        onDurationChange(audio.duration);
      }
    };

    const handleLoadedMetadata = () => {
      if (audio.duration) {
        onDurationChange(audio.duration);
      }
    };

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    
    // Update playback rate when it changes
    audio.playbackRate = playbackRate;

    audio.addEventListener('timeupdate', handleTimeUpdate);
    audio.addEventListener('durationchange', handleDurationChange);
    audio.addEventListener('loadedmetadata', handleLoadedMetadata);
    audio.addEventListener('play', handlePlay);
    audio.addEventListener('pause', handlePause);

    return () => {
      audio.removeEventListener('timeupdate', handleTimeUpdate);
      audio.removeEventListener('durationchange', handleDurationChange);
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
      audio.removeEventListener('play', handlePlay);
      audio.removeEventListener('pause', handlePause);
    };
  }, [onTimeUpdate, onDurationChange, playbackRate]);

  // Handle external seeks (from transcript clicks or programmatic seeks)
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || isSeekingRef.current) {
      return;
    }

    const lastExternalTime = lastExternalTimeRef.current;
    const timeDiff = Math.abs(currentTime - lastExternalTime);
    const audioTimeDiff = Math.abs(audio.currentTime - currentTime);

    // If currentTime changed significantly from the last external time, it's an external seek
    if (timeDiff > 0.5 && audioTimeDiff > 0.3) {
      audio.currentTime = currentTime;
      // Start playing if paused (user clicked on transcript to jump to that point)
      if (audio.paused) {
        audio.play().catch(() => {
          // Ignore play errors (e.g., browser autoplay restrictions)
        });
      }
      lastExternalTimeRef.current = currentTime;
    } else if (audioTimeDiff > 0.2 && timeDiff < 0.1) {
      // Small sync adjustment when external time hasn't changed much but audio is out of sync
      audio.currentTime = currentTime;
    }
  }, [currentTime]);

  const handlePlayPause = () => {
    const audio = audioRef.current;
    if (!audio) return;

    if (audio.paused) {
      audio.play().catch((err) => {
        console.error('Error playing audio:', err);
      });
    } else {
      audio.pause();
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newTime = parseFloat(e.target.value);
    isSeekingRef.current = true;
    onSeek(newTime);
    if (audioRef.current) {
      audioRef.current.currentTime = newTime;
    }
    // Reset seeking flag after a brief delay
    setTimeout(() => {
      isSeekingRef.current = false;
    }, 100);
  };

  const handlePlaybackRateChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newRate = parseFloat(e.target.value);
    setPlaybackRate(newRate);
    if (audioRef.current) {
      audioRef.current.playbackRate = newRate;
    }
  };

  const formatTime = (seconds: number): string => {
    if (isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="audio-player">
      <audio ref={audioRef} src={audioUrl} />
      {filename && (
        <div className={`audio-filename ${isStuck ? 'hidden' : ''}`}>
          {filename}
        </div>
      )}
      <div className="audio-controls">
        <button onClick={handlePlayPause} className="play-pause-button" type="button">
          <span style={{ display: 'inline-block', lineHeight: 1 }}>{isPlaying ? '⏸' : '▶'}</span>
        </button>
        <div className="progress-container">
          <span className="time-display">{formatTime(currentTime)}</span>
          <input
            type="range"
            min="0"
            max={duration || 0}
            step="0.1"
            value={currentTime}
            onChange={handleSeek}
            className="progress-slider"
          />
          <span className="time-display">{formatTime(duration)}</span>
        </div>
        <div className="playback-speed-control">
          <label htmlFor="playback-speed" className="speed-label">Speed:</label>
          <select
            id="playback-speed"
            value={playbackRate}
            onChange={handlePlaybackRateChange}
            className="speed-select"
          >
            <option value="0.5">0.5x</option>
            <option value="0.75">0.75x</option>
            <option value="1">1x</option>
            <option value="1.5">1.5x</option>
          </select>
        </div>
      </div>
    </div>
  );
}
