/** Type definitions for the application. */

export interface TranscriptSegment {
  text: string;
  translation: string;
  start: number;
  end: number;
}

export interface ProcessRequest {
  url: string;
  source_language: string;
  target_language: string;
}

export interface ProcessResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface StatusResponse {
  job_id: string;
  status: "queued" | "processing" | "completed" | "error";
  progress?: number;
  message?: string;
}

export interface ResultResponse {
  job_id: string;
  audio_url: string;
  segments: TranscriptSegment[];
  source_language: string;
  target_language: string;
  filename?: string;
}

export type LanguageCode = 
  | "en"  // English
  | "ja"  // Japanese
  | "zh"; // Chinese

export interface LanguageOption {
  code: LanguageCode;
  name: string;
}

