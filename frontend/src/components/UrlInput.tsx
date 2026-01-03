import { useState, useRef, useEffect } from 'react';
import { LanguageCode } from '../types';
import LanguageSelect from './LanguageSelect';

interface UrlInputProps {
  onSubmit: (url: string, sourceLanguage: LanguageCode, targetLanguage: LanguageCode) => void;
  onFileSubmit: (file: File, sourceLanguage: LanguageCode, targetLanguage: LanguageCode) => void;
  onRecordingSubmit: (file: File, sourceLanguage: LanguageCode, targetLanguage: LanguageCode) => void;
  disabled?: boolean;
  initialUrl?: string;
  initialSourceLanguage?: LanguageCode;
  initialTargetLanguage?: LanguageCode;
}

export default function UrlInput({ 
  onSubmit, 
  onFileSubmit,
  onRecordingSubmit,
  disabled, 
  initialUrl = '', 
  initialSourceLanguage = 'ja',
  initialTargetLanguage = 'en'
}: UrlInputProps) {
  const [url, setUrl] = useState(initialUrl);
  const [sourceLanguage, setSourceLanguage] = useState<LanguageCode>(initialSourceLanguage);
  const [targetLanguage, setTargetLanguage] = useState<LanguageCode>(initialTargetLanguage);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [inputMode, setInputMode] = useState<'url' | 'file' | 'record'>('url');
  
  // Recording state
  const MAX_RECORDING_TIME = 300; // 5 minutes in seconds
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);

  // Supported translation pairs: ja->en, zh->en, en->ja, en->zh
  const getSupportedTargetLanguages = (source: LanguageCode): LanguageCode[] => {
    if (source === 'ja' || source === 'zh') {
      return ['en']; // Japanese and Chinese can only translate to English
    }
    if (source === 'en') {
      return ['ja', 'zh']; // English can translate to Japanese or Chinese
    }
    return [];
  };

  const supportedTargetLanguages = getSupportedTargetLanguages(sourceLanguage);
  const isSupportedPair = supportedTargetLanguages.includes(targetLanguage);
  const isSameLanguage = sourceLanguage === targetLanguage;
  const isValidPair = !isSameLanguage && isSupportedPair;

  // Auto-adjust target language if current selection is not supported
  const handleSourceLanguageChange = (value: LanguageCode) => {
    setSourceLanguage(value);
    const newSupportedTargets = getSupportedTargetLanguages(value);
    if (!newSupportedTargets.includes(targetLanguage)) {
      // Auto-select first supported target language
      setTargetLanguage(newSupportedTargets[0]);
    }
  };

  const handleUrlSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (url.trim() && !disabled && isValidPair) {
      onSubmit(url.trim(), sourceLanguage, targetLanguage);
    }
  };

  const handleFileSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedFile && !disabled && isValidPair) {
      onFileSubmit(selectedFile, sourceLanguage, targetLanguage);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      // Validate that it's an audio file
      if (!file.type.startsWith('audio/')) {
        setFileError('Only audio files are supported. Please select an audio file (e.g., .mp3, .wav, .m4a, .ogg).');
        setSelectedFile(null);
        // Clear the input
        e.target.value = '';
        return;
      }
      setFileError(null);
      setSelectedFile(file);
    } else {
      setFileError(null);
      setSelectedFile(null);
    }
  };

  // Recording functions
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4'
      });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];
      
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };
      
      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mediaRecorder.mimeType });
        setRecordedBlob(blob);
        // Stop all tracks
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop());
          streamRef.current = null;
        }
      };
      
      mediaRecorder.start();
      setIsRecording(true);
      setRecordingTime(0);
      
      // Start timer
      timerRef.current = window.setInterval(() => {
        setRecordingTime(prev => {
          const newTime = prev + 1;
          // Auto-stop at 5 minutes
          if (newTime >= MAX_RECORDING_TIME) {
            // Stop recording if still active
            if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
              mediaRecorderRef.current.stop();
              setIsRecording(false);
              if (timerRef.current !== null) {
                clearInterval(timerRef.current);
                timerRef.current = null;
              }
            }
            return MAX_RECORDING_TIME;
          }
          return newTime;
        });
      }, 1000);
    } catch (error) {
      console.error('Error starting recording:', error);
      alert('Failed to access microphone. Please check your permissions.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current !== null) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  };

  const handleRecordingSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (recordedBlob && !disabled && isValidPair) {
      // Convert blob to File
      const file = new File([recordedBlob], `recording_${Date.now()}.${mediaRecorderRef.current?.mimeType.includes('webm') ? 'webm' : 'mp4'}`, {
        type: recordedBlob.type
      });
      onRecordingSubmit(file, sourceLanguage, targetLanguage);
    }
  };

  const resetRecording = () => {
    setRecordedBlob(null);
    setRecordingTime(0);
    chunksRef.current = [];
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    if (timerRef.current !== null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  // Cleanup on unmount or mode change
  useEffect(() => {
    if (inputMode !== 'record') {
      // Stop recording if active
      if (mediaRecorderRef.current && isRecording) {
        mediaRecorderRef.current.stop();
      }
      resetRecording();
    }
    return () => {
      if (timerRef.current !== null) {
        clearInterval(timerRef.current);
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inputMode]);

  // Format time as MM:SS
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="input-container">
      <div className="input-mode-selector">
        <button
          type="button"
          className={`mode-button ${inputMode === 'url' ? 'active' : ''}`}
          onClick={() => setInputMode('url')}
          disabled={disabled}
        >
          URL
        </button>
        <button
          type="button"
          className={`mode-button ${inputMode === 'file' ? 'active' : ''}`}
          onClick={() => setInputMode('file')}
          disabled={disabled}
        >
          Upload
        </button>
        <button
          type="button"
          className={`mode-button ${inputMode === 'record' ? 'active' : ''}`}
          onClick={() => setInputMode('record')}
          disabled={disabled}
        >
          Record
        </button>
      </div>

      {inputMode === 'url' ? (
        <form onSubmit={handleUrlSubmit} className="url-input-form">
          <div className="input-group">
            <label htmlFor="url-input">Audio URL</label>
            <input
              id="url-input"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/audio.mp3"
              title="Enter URL to an audio file (e.g., .mp3, .wav, .m4a, .ogg). Video files are not supported."
              disabled={disabled}
              required
            />
          </div>
          <div className="language-selects-container">
            <div className="input-group">
              <label htmlFor="source-language-select">Source Language</label>
              <LanguageSelect
                id="source-language-select"
                value={sourceLanguage}
                onChange={handleSourceLanguageChange}
                disabled={disabled}
              />
            </div>
            <div className="input-group">
              <label htmlFor="target-language-select">Target Language</label>
              <LanguageSelect
                id="target-language-select"
                value={targetLanguage}
                onChange={(value) => setTargetLanguage(value)}
                disabled={disabled}
                allowedLanguages={supportedTargetLanguages}
              />
            </div>
          </div>
          {isSameLanguage && (
            <div className="error-message" style={{ color: '#d32f2f', fontSize: '0.875rem', marginBottom: '0.5rem' }}>
              Source and target languages cannot be the same
            </div>
          )}
          {!isSupportedPair && !isSameLanguage && (
            <div className="error-message" style={{ color: '#d32f2f', fontSize: '0.875rem', marginBottom: '0.5rem' }}>
              This language pair is not supported. Supported pairs: Japanese→English, Chinese→English, English→Japanese, English→Chinese
            </div>
          )}
          <button type="submit" disabled={disabled || !url.trim() || !isValidPair}>
            Let's go!
          </button>
        </form>
      ) : inputMode === 'file' ? (
        <form onSubmit={handleFileSubmit} className="url-input-form">
          <div className="input-group">
            <label htmlFor="file-input">Select Audio File</label>
            <input
              id="file-input"
              type="file"
              accept="audio/*"
              onChange={handleFileChange}
              disabled={disabled}
              required
            />
            {fileError && (
              <div className="error-message" style={{ color: '#d32f2f', fontSize: '0.875rem', marginTop: '0.5rem' }}>
                {fileError}
              </div>
            )}
            {selectedFile && (
              <div className="file-info">
                <span className="file-name">{selectedFile.name}</span>
                <span className="file-size">
                  {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                </span>
              </div>
            )}
          </div>
          <div className="language-selects-container">
            <div className="input-group">
              <label htmlFor="source-language-select-file">Source Language</label>
              <LanguageSelect
                id="source-language-select-file"
                value={sourceLanguage}
                onChange={handleSourceLanguageChange}
                disabled={disabled}
              />
            </div>
            <div className="input-group">
              <label htmlFor="target-language-select-file">Target Language</label>
              <LanguageSelect
                id="target-language-select-file"
                value={targetLanguage}
                onChange={(value) => setTargetLanguage(value)}
                disabled={disabled}
                allowedLanguages={supportedTargetLanguages}
              />
            </div>
          </div>
          {isSameLanguage && (
            <div className="error-message" style={{ color: '#d32f2f', fontSize: '0.875rem', marginBottom: '0.5rem' }}>
              Source and target languages cannot be the same
            </div>
          )}
          {!isSupportedPair && !isSameLanguage && (
            <div className="error-message" style={{ color: '#d32f2f', fontSize: '0.875rem', marginBottom: '0.5rem' }}>
              This language pair is not supported. Supported pairs: Japanese→English, Chinese→English, English→Japanese, English→Chinese
            </div>
          )}
          <button type="submit" disabled={disabled || !selectedFile || !isValidPair || !!fileError}>
            Process
          </button>
        </form>
      ) : (
        <form onSubmit={handleRecordingSubmit} className="url-input-form">
          <div className="input-group">
            <label htmlFor="recording-controls">Record Audio (Max 5 minutes)</label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', alignItems: 'center' }}>
              {!recordedBlob ? (
                <>
                  {!isRecording ? (
                    <>
                      <button
                        type="button"
                        onClick={startRecording}
                        disabled={disabled}
                        style={{
                          padding: '1rem 2rem',
                          fontSize: '1.1rem',
                          backgroundColor: '#d32f2f',
                          color: 'white',
                          border: 'none',
                          borderRadius: '8px',
                          cursor: disabled ? 'not-allowed' : 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.5rem'
                        }}
                      >
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                          <circle cx="12" cy="12" r="10" />
                        </svg>
                        Start Recording
                      </button>
                      <div style={{ fontSize: '0.875rem', color: '#666', textAlign: 'center' }}>
                        Maximum recording time: 5 minutes
                      </div>
                    </>
                  ) : (
                    <>
                      <div style={{ fontSize: '2rem', fontWeight: 'bold', color: recordingTime >= MAX_RECORDING_TIME ? '#d32f2f' : recordingTime >= MAX_RECORDING_TIME - 30 ? '#ff9800' : '#d32f2f' }}>
                        {formatTime(recordingTime)}
                      </div>
                      {recordingTime >= MAX_RECORDING_TIME && (
                        <div style={{ color: '#d32f2f', fontSize: '0.9rem', fontWeight: 'bold', marginTop: '0.5rem' }}>
                          Maximum recording time reached (5 minutes)
                        </div>
                      )}
                      {recordingTime >= MAX_RECORDING_TIME - 30 && recordingTime < MAX_RECORDING_TIME && (
                        <div style={{ color: '#ff9800', fontSize: '0.9rem', marginTop: '0.5rem' }}>
                          {MAX_RECORDING_TIME - recordingTime} seconds remaining
                        </div>
                      )}
                      <button
                        type="button"
                        onClick={stopRecording}
                        disabled={disabled || recordingTime >= MAX_RECORDING_TIME}
                        style={{
                          padding: '1rem 2rem',
                          fontSize: '1.1rem',
                          backgroundColor: recordingTime >= MAX_RECORDING_TIME ? '#999' : '#666',
                          color: 'white',
                          border: 'none',
                          borderRadius: '8px',
                          cursor: (disabled || recordingTime >= MAX_RECORDING_TIME) ? 'not-allowed' : 'pointer'
                        }}
                      >
                        {recordingTime >= MAX_RECORDING_TIME ? 'Recording Stopped' : 'Stop Recording'}
                      </button>
                    </>
                  )}
                </>
              ) : (
                <>
                  <div style={{ fontSize: '1.1rem', color: '#666' }}>
                    Recording complete ({formatTime(recordingTime)})
                  </div>
                  <button
                    type="button"
                    onClick={resetRecording}
                    disabled={disabled}
                    style={{
                      padding: '0.5rem 1rem',
                      fontSize: '0.9rem',
                      backgroundColor: '#999',
                      color: 'white',
                      border: 'none',
                      borderRadius: '6px',
                      cursor: disabled ? 'not-allowed' : 'pointer'
                    }}
                  >
                    Record Again
                  </button>
                </>
              )}
            </div>
          </div>
          <div className="language-selects-container">
            <div className="input-group">
              <label htmlFor="source-language-select-record">Source Language</label>
              <LanguageSelect
                id="source-language-select-record"
                value={sourceLanguage}
                onChange={handleSourceLanguageChange}
                disabled={disabled}
              />
            </div>
            <div className="input-group">
              <label htmlFor="target-language-select-record">Target Language</label>
              <LanguageSelect
                id="target-language-select-record"
                value={targetLanguage}
                onChange={(value) => setTargetLanguage(value)}
                disabled={disabled}
                allowedLanguages={supportedTargetLanguages}
              />
            </div>
          </div>
          {isSameLanguage && (
            <div className="error-message" style={{ color: '#d32f2f', fontSize: '0.875rem', marginBottom: '0.5rem' }}>
              Source and target languages cannot be the same
            </div>
          )}
          {!isSupportedPair && !isSameLanguage && (
            <div className="error-message" style={{ color: '#d32f2f', fontSize: '0.875rem', marginBottom: '0.5rem' }}>
              This language pair is not supported. Supported pairs: Japanese→English, Chinese→English, English→Japanese, English→Chinese
            </div>
          )}
          <button type="submit" disabled={disabled || !recordedBlob || !isValidPair}>
            Process
          </button>
        </form>
      )}
    </div>
  );
}
