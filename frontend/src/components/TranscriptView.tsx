import { useEffect, useRef } from 'react';
import { TranscriptSegment } from '../types';

interface TranscriptViewProps {
  segments: TranscriptSegment[];
  currentTime: number;
  onSeek: (time: number) => void;
  sourceLanguage: string;
  targetLanguage: string;
}

export default function TranscriptView({
  segments,
  currentTime,
  onSeek,
  sourceLanguage,
  targetLanguage,
}: TranscriptViewProps) {
  const activeSegmentRef = useRef<HTMLDivElement>(null);

  // Find the current segment based on playback time
  const getCurrentSegmentIndex = (): number => {
    return segments.findIndex(
      (seg) => currentTime >= seg.start && currentTime <= seg.end
    );
  };

  const currentIndex = getCurrentSegmentIndex();

  // Scroll to active segment
  useEffect(() => {
    if (activeSegmentRef.current) {
      activeSegmentRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  }, [currentIndex]);

  const handleSegmentClick = (segment: TranscriptSegment) => {
    onSeek(segment.start);
  };

  const toGoogleTranslateLanguageCode = (lang: string): string => {
    // Convert language codes to Google Translate format
    if (lang === 'zh') {
      return 'zh-CN';
    }
    return lang;
  };

  const getGoogleTranslateUrl = (text: string): string => {
    const encodedText = encodeURIComponent(text);
    const sourceLang = toGoogleTranslateLanguageCode(sourceLanguage);
    const targetLang = toGoogleTranslateLanguageCode(targetLanguage);
    return `https://translate.google.com/?sl=${sourceLang}&tl=${targetLang}&text=${encodedText}`;
  };

  return (
    <div className="transcript-view">
      <div className="transcript-header">
        <div className="transcript-column original-column">
          <h3>Original Audio</h3>
        </div>
        <div className="transcript-column translation-column">
          <h3>Translation</h3>
        </div>
      </div>
      <div className="transcript-content">
        {segments.map((segment, index) => {
          const isActive = index === currentIndex;
          return (
            <div
              key={index}
              ref={isActive ? activeSegmentRef : null}
              className={`transcript-segment ${isActive ? 'active' : ''}`}
              onClick={() => handleSegmentClick(segment)}
            >
              <div className="transcript-column original-column">
                <div className="segment-text">{segment.text}</div>
                <div className="segment-time">
                  {formatTime(segment.start)} - {formatTime(segment.end)}
                </div>
              </div>
              <div className="transcript-column translation-column">
                <div className="segment-text-container">
                  <div className="segment-text">{segment.translation}</div>
                  <a
                    href={getGoogleTranslateUrl(segment.text)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="google-translate-link"
                    onClick={(e) => e.stopPropagation()}
                    title="Translate with Google Translate"
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M12.87 15.07l-2.54-2.51.03-.03c1.74-1.94 2.98-4.17 3.71-6.53H17V4h-7V2H8v2H1v1.99h11.17C11.5 7.92 10.44 9.75 9 11.35 8.07 10.32 7.3 9.19 6.69 8h-2c.73 1.63 1.73 3.17 2.98 4.56l-5.09 5.02L4 19l5-5 3.11 3.11.76-2.04zM18.5 10h-2L12 22h2l1.12-3h4.75L21 22h2l-4.5-12zm-2.62 7l1.62-4.33L19.12 17h-3.24z" fill="currentColor"/>
                    </svg>
                  </a>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function formatTime(seconds: number): string {
  if (isNaN(seconds)) return '0:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

