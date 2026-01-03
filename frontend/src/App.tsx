import { useState, useEffect, useRef, useCallback } from 'react';
import UrlInput from './components/UrlInput';
import AudioPlayer from './components/AudioPlayer';
import TranscriptView from './components/TranscriptView';
import LoadingIndicator from './components/LoadingIndicator';
import { processUrl, processFile, processRecording, getStatus, getResult, calculateFileHash, checkCache } from './api';
import { LanguageCode, TranscriptSegment, ResultResponse } from './types';
import kikuLogo from './images/kiku_logo.png';
import './App.css';

type AppState = 'idle' | 'processing' | 'completed' | 'error';

function App() {
  const [state, setState] = useState<AppState>('idle');
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ResultResponse | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isPlayerStuck, setIsPlayerStuck] = useState(false);
  const playerSectionRef = useRef<HTMLDivElement>(null);
  const isRequestPending = useRef(false);
  
  // Store uploaded file for blob URL playback
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [fileBlobUrl, setFileBlobUrl] = useState<string | null>(null);
  
  // Track original URL and languages for URL-based jobs (for deep linking)
  const [originalUrl, setOriginalUrl] = useState<string | null>(null);
  const [originalSourceLanguage, setOriginalSourceLanguage] = useState<LanguageCode | null>(null);
  const [originalTargetLanguage, setOriginalTargetLanguage] = useState<LanguageCode | null>(null);

  // Poll for status updates
  useEffect(() => {
    if (!jobId || state !== 'processing') {
      console.log('Polling skipped - jobId:', jobId, 'state:', state);
      return;
    }

    console.log('Starting status polling for jobId:', jobId);
    let pollInterval: ReturnType<typeof setInterval> | null = null;
    let cancelled = false;

    // Immediate status check
    const checkStatus = async () => {
      // Skip if a request is already pending
      if (isRequestPending.current) {
        console.log('Status check skipped - previous request still pending');
        return false;
      }

      isRequestPending.current = true;
      try {
        console.log('Checking status for jobId:', jobId);
        const status = await getStatus(jobId!);
        isRequestPending.current = false;
        if (cancelled) return true;

        console.log('Status update received:', status);
        setProgress(status.progress || 0);
        setStatusMessage(status.message || status.status || 'Processing...');

        if (status.status === 'completed') {
          const resultData = await getResult(jobId!);
          setResult(resultData);
          setState('completed');
          return true; // Indicate we're done
        } else if (status.status === 'error') {
          setError(status.message || 'Processing failed');
          setState('error');
          return true; // Indicate we're done
        }
      } catch (err) {
        isRequestPending.current = false;
        if (cancelled) return true;
        console.error('Error checking status:', err);
        setError('Something went wrong. Please try again.');
        setState('error');
        return true; // Indicate we're done
      }
      return false; // Continue polling
    };

    // Check immediately, then start polling
    checkStatus().then((done) => {
      if (done || cancelled) return;

      // Then poll every second
      pollInterval = setInterval(async () => {
        if (cancelled) return;
        const isDone = await checkStatus();
        if (isDone && pollInterval) {
          clearInterval(pollInterval);
          pollInterval = null;
        }
      }, 1000);
    });

    return () => {
      cancelled = true;
      isRequestPending.current = false;
      if (pollInterval) {
        clearInterval(pollInterval);
      }
    };
  }, [jobId, state]);

  const handleSubmit = async (url: string, sourceLanguage: LanguageCode, targetLanguage: LanguageCode) => {
    try {
      setState('processing');
      setError(null);
      setProgress(0);
      setStatusMessage('Starting processing...');
      setResult(null);
      setCurrentTime(0);
      setDuration(0);
      
      // Store original URL and languages for deep linking
      setOriginalUrl(url.trim());
      setOriginalSourceLanguage(sourceLanguage);
      setOriginalTargetLanguage(targetLanguage);
      
      // Clear uploaded file state for URL jobs
      if (fileBlobUrl) {
        URL.revokeObjectURL(fileBlobUrl);
        setFileBlobUrl(null);
      }
      setUploadedFile(null);

      const response = await processUrl({ url, source_language: sourceLanguage, target_language: targetLanguage });
      setJobId(response.job_id);
      
      // Immediately check status to get the latest update
      try {
        console.log('Fetching initial status for jobId:', response.job_id);
        const initialStatus = await getStatus(response.job_id);
        console.log('Initial status received:', initialStatus);
        setProgress(initialStatus.progress || 0);
        setStatusMessage(initialStatus.message || initialStatus.status || 'Processing...');
      } catch (err) {
        console.error('Error fetching initial status:', err);
        // Continue with polling even if initial check fails
      }
    } catch (err) {
      console.error('Error processing URL:', err);
      setError(err instanceof Error ? err.message : 'Failed to process URL');
      setState('error');
    }
  };

  const handleFileSubmit = async (file: File, sourceLanguage: LanguageCode, targetLanguage: LanguageCode) => {
    try {
      setState('processing');
      setError(null);
      setProgress(0);
      setStatusMessage('Calculating file hash...');
      setResult(null);
      setCurrentTime(0);
      setDuration(0);
      
      // Clear original URL/languages for file uploads (no deep linking)
      setOriginalUrl(null);
      setOriginalSourceLanguage(null);
      setOriginalTargetLanguage(null);
      
      // Store the file for blob URL playback
      setUploadedFile(file);
      // Create blob URL immediately
      const blobUrl = URL.createObjectURL(file);
      setFileBlobUrl(blobUrl);

      // Calculate file hash before upload
      const fileHash = await calculateFileHash(file);
      setStatusMessage('Checking cache...');
      
      // Check if cache exists (optional - just for feedback, we still upload for playback)
      const cacheCheck = await checkCache(fileHash, sourceLanguage, targetLanguage);
      if (cacheCheck.exists) {
        setStatusMessage('Cache found, uploading file for playback...');
      } else {
        setStatusMessage('No cache found, processing required...');
      }

      const response = await processFile(file, sourceLanguage, targetLanguage);
      setJobId(response.job_id);
      
      // Immediately check status to get the latest update
      try {
        const initialStatus = await getStatus(response.job_id);
        console.log('Initial status (file):', initialStatus);
        setProgress(initialStatus.progress || 0);
        setStatusMessage(initialStatus.message || initialStatus.status || 'Processing...');
      } catch (err) {
        console.error('Error fetching initial status:', err);
        // Continue with polling even if initial check fails
      }
    } catch (err) {
      console.error('Error processing file:', err);
      setError(err instanceof Error ? err.message : 'Failed to process file');
      setState('error');
      // Clean up blob URL on error
      if (fileBlobUrl) {
        URL.revokeObjectURL(fileBlobUrl);
        setFileBlobUrl(null);
      }
      setUploadedFile(null);
    }
  };

  const handleRecordingSubmit = async (file: File, sourceLanguage: LanguageCode, targetLanguage: LanguageCode) => {
    try {
      setState('processing');
      setError(null);
      setProgress(0);
      setStatusMessage('Processing recording...');
      setResult(null);
      setCurrentTime(0);
      setDuration(0);
      
      // Clear original URL/languages for recordings (no deep linking)
      setOriginalUrl(null);
      setOriginalSourceLanguage(null);
      setOriginalTargetLanguage(null);
      
      // Store the file for blob URL playback
      setUploadedFile(file);
      // Create blob URL immediately
      const blobUrl = URL.createObjectURL(file);
      setFileBlobUrl(blobUrl);

      // Recordings don't check cache - process directly
      const response = await processRecording(file, sourceLanguage, targetLanguage);
      setJobId(response.job_id);
      
      // Immediately check status to get the latest update
      try {
        const initialStatus = await getStatus(response.job_id);
        console.log('Initial status (recording):', initialStatus);
        setProgress(initialStatus.progress || 0);
        setStatusMessage(initialStatus.message || initialStatus.status || 'Processing...');
      } catch (err) {
        console.error('Error fetching initial status:', err);
        // Continue with polling even if initial check fails
      }
    } catch (err) {
      console.error('Error processing recording:', err);
      setError(err instanceof Error ? err.message : 'Failed to process recording');
      setState('error');
      // Clean up blob URL on error
      if (fileBlobUrl) {
        URL.revokeObjectURL(fileBlobUrl);
        setFileBlobUrl(null);
      }
      setUploadedFile(null);
    }
  };

  const handleTimeUpdate = (time: number) => {
    setCurrentTime(time);
  };

  const handleDurationChange = (dur: number) => {
    setDuration(dur);
  };

  const handleSeek = (time: number) => {
    setCurrentTime(time);
  };

  const handleReset = () => {
    setState('idle');
    setJobId(null);
    setProgress(0);
    setStatusMessage('');
    setError(null);
    setResult(null);
    setCurrentTime(0);
    setDuration(0);
    setIsPlayerStuck(false);
    
    // Clear original URL/languages
    setOriginalUrl(null);
    setOriginalSourceLanguage(null);
    setOriginalTargetLanguage(null);
    
    // Clear query parameter state to prevent auto-processing
    setQueryUrl(null);
    setQuerySourceLanguage(null);
    setQueryTargetLanguage(null);
    setHasProcessedQueryParams(false);
    
    // Clean up blob URL
    if (fileBlobUrl) {
      URL.revokeObjectURL(fileBlobUrl);
      setFileBlobUrl(null);
    }
    setUploadedFile(null);
    
    // Clear URL query parameters
    window.history.replaceState({}, '', window.location.pathname);
  };

  // Clean up blob URL on unmount
  useEffect(() => {
    return () => {
      if (fileBlobUrl) {
        URL.revokeObjectURL(fileBlobUrl);
      }
    };
  }, [fileBlobUrl]);

  // Read URL query parameters on mount
  const [queryUrl, setQueryUrl] = useState<string | null>(null);
  const [querySourceLanguage, setQuerySourceLanguage] = useState<LanguageCode | null>(null);
  const [queryTargetLanguage, setQueryTargetLanguage] = useState<LanguageCode | null>(null);
  const [hasProcessedQueryParams, setHasProcessedQueryParams] = useState(false);
  
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlParam = params.get('u'); // Use 'u' instead of 'url' to work around Vite bug #19795
    const sourceLanguageParam = params.get('source') as LanguageCode | null;
    const targetLanguageParam = params.get('target') as LanguageCode | null;
    
    // Validate language codes
    const validLanguages: LanguageCode[] = ['en', 'ja', 'zh'];
    const validSourceLanguage = sourceLanguageParam && validLanguages.includes(sourceLanguageParam) 
      ? sourceLanguageParam 
      : null;
    const validTargetLanguage = targetLanguageParam && validLanguages.includes(targetLanguageParam)
      ? targetLanguageParam
      : null;
    
    if (urlParam) {
      setQueryUrl(urlParam);
    }
    if (validSourceLanguage) {
      setQuerySourceLanguage(validSourceLanguage);
    }
    if (validTargetLanguage) {
      setQueryTargetLanguage(validTargetLanguage);
    }
  }, []);

  // Auto-process URL from query parameters on mount
  useEffect(() => {
    if (state === 'idle' && queryUrl && querySourceLanguage && queryTargetLanguage && !hasProcessedQueryParams) {
      setHasProcessedQueryParams(true);
      handleSubmit(queryUrl, querySourceLanguage, queryTargetLanguage);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, queryUrl, querySourceLanguage, queryTargetLanguage, hasProcessedQueryParams]);

  // Update URL when transcript view is displayed (for URL-based jobs only)
  useEffect(() => {
    if (state === 'completed' && result && originalUrl && originalSourceLanguage && originalTargetLanguage) {
      const params = new URLSearchParams();
      params.set('u', originalUrl); // Use 'u' instead of 'url' to work around Vite bug #19795
      params.set('source', originalSourceLanguage);
      params.set('target', originalTargetLanguage);
      const newUrl = `${window.location.pathname}?${params.toString()}`;
      window.history.replaceState({}, '', newUrl);
    }
  }, [state, result, originalUrl, originalSourceLanguage, originalTargetLanguage]);

  // Detect when player section becomes sticky
  useEffect(() => {
    if (state !== 'completed' || !playerSectionRef.current) return;

    const playerSection = playerSectionRef.current;
    const checkSticky = () => {
      const rect = playerSection.getBoundingClientRect();
      // If the top of the element is at or near the top of the viewport (within 1px), it's stuck
      setIsPlayerStuck(rect.top <= 1);
    };

    // Check on mount
    checkSticky();

    // Check on scroll
    window.addEventListener('scroll', checkSticky, { passive: true });
    window.addEventListener('resize', checkSticky);

    return () => {
      window.removeEventListener('scroll', checkSticky);
      window.removeEventListener('resize', checkSticky);
    };
  }, [state]);

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <div className="header-center">
            <img src={kikuLogo} alt="Kiku Logo" className="header-logo" />
            <p className="header-subtitle">Learn through translated audio</p>
          </div>
          {state === 'completed' && (
            <button onClick={handleReset} className="new-file-button" title="Process New File">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 5V19M5 12H19" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          )}
        </div>
      </header>

      <main className="app-main">
        {state === 'idle' && (
          <div className="input-section">
            <UrlInput 
              onSubmit={handleSubmit} 
              onFileSubmit={handleFileSubmit}
              onRecordingSubmit={handleRecordingSubmit}
              disabled={false}
              initialUrl={queryUrl || undefined}
              initialSourceLanguage={querySourceLanguage || undefined}
              initialTargetLanguage={queryTargetLanguage || undefined}
            />
          </div>
        )}

        {state === 'processing' && (
          <div className="processing-section">
            <LoadingIndicator message={statusMessage} progress={progress} />
            {error && <div className="error-message">{error}</div>}
          </div>
        )}

        {state === 'error' && (
          <div className="error-section">
            <div className="error-message">{error}</div>
            <button onClick={handleReset} className="reset-button">
              Try Again
            </button>
          </div>
        )}

        {state === 'completed' && result && (
          <div className="result-section">
            <div className={`player-section ${isPlayerStuck ? 'stuck' : ''}`} ref={playerSectionRef}>
              <AudioPlayer
                audioUrl={fileBlobUrl || (result.audio_url.startsWith('http') 
                  ? result.audio_url 
                  : `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}${result.audio_url}`)}
                currentTime={currentTime}
                duration={duration}
                onTimeUpdate={handleTimeUpdate}
                onDurationChange={handleDurationChange}
                onSeek={handleSeek}
                filename={result.filename}
                isStuck={isPlayerStuck}
              />
            </div>
            <div className="transcript-section">
              <TranscriptView
                segments={result.segments}
                currentTime={currentTime}
                onSeek={handleSeek}
                sourceLanguage={result.source_language}
                targetLanguage={result.target_language}
              />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;

