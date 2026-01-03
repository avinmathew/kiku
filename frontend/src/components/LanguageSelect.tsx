import { useState, useRef, useEffect } from 'react';
import { LanguageCode, LanguageOption } from '../types';
import { GB, JP, CN } from 'country-flag-icons/react/3x2';

const LANGUAGE_COUNTRIES: Record<LanguageCode, string> = {
  en: 'GB',
  ja: 'JP',
  zh: 'CN',
};

const FLAG_COMPONENTS: Record<string, React.ComponentType<any>> = {
  GB,
  JP,
  CN,
};

const LANGUAGES: LanguageOption[] = [
  { code: 'en', name: 'English' },
  { code: 'ja', name: 'Japanese' },
  { code: 'zh', name: 'Chinese' },
];

interface LanguageSelectProps {
  value: LanguageCode;
  onChange: (value: LanguageCode) => void;
  disabled?: boolean;
  id?: string;
  allowedLanguages?: LanguageCode[]; // Optional filter for allowed languages
}

export default function LanguageSelect({
  value,
  onChange,
  disabled = false,
  id,
  allowedLanguages,
}: LanguageSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Filter languages if allowedLanguages is provided
  const availableLanguages = allowedLanguages 
    ? LANGUAGES.filter(lang => allowedLanguages.includes(lang.code))
    : LANGUAGES;

  const selectedLanguage = availableLanguages.find((lang) => lang.code === value) || availableLanguages[0];
  const selectedCountry = LANGUAGE_COUNTRIES[value];
  const FlagIcon = FLAG_COMPONENTS[selectedCountry];

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [isOpen]);

  const handleSelect = (code: LanguageCode) => {
    onChange(code);
    setIsOpen(false);
  };

  return (
    <div className="language-select-container" ref={containerRef}>
      <button
        type="button"
        id={id}
        className={`language-select-button ${isOpen ? 'open' : ''} ${disabled ? 'disabled' : ''}`}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
      >
        <span className="language-select-value">
          <span className="language-flag">
            <FlagIcon className="flag-icon" />
          </span>
          <span className="language-name">{selectedLanguage.name}</span>
        </span>
        <span className="language-select-arrow">▼</span>
      </button>
      {isOpen && (
        <div className="language-select-dropdown">
          {availableLanguages.map((lang) => {
            const countryCode = LANGUAGE_COUNTRIES[lang.code];
            const LangFlagIcon = FLAG_COMPONENTS[countryCode];
            return (
              <button
                key={lang.code}
                type="button"
                className={`language-select-option ${value === lang.code ? 'selected' : ''}`}
                onClick={() => handleSelect(lang.code)}
              >
                <span className="language-flag">
                  <LangFlagIcon className="flag-icon" />
                </span>
                <span className="language-name">{lang.name}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
