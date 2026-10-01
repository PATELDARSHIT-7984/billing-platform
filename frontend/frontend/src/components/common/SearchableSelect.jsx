import { useEffect, useMemo, useRef, useState } from 'react';
import './SearchableSelect.css';

export default function SearchableSelect({
  label,
  name,
  options = [],
  value,
  onChange,
  placeholder = 'Search...',
  required = false,
  error = '',
  disabled = false,
  allowCustom = false,
  emptyMessage = 'No matches found.',
}) {
  const containerRef = useRef(null);
  const [inputText, setInputText] = useState('');
  const [open, setOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(0);
  const [customOptions, setCustomOptions] = useState([]);

  const allOptions = useMemo(
    () => [...options, ...customOptions],
    [options, customOptions],
  );

  const selectedOption = useMemo(
    () => allOptions.find((option) => String(option.value) === String(value)) || null,
    [allOptions, value],
  );

  useEffect(() => {
    setInputText(selectedOption?.label || '');
  }, [selectedOption?.label]);

  useEffect(() => {
    const handleOutside = (event) => {
      if (!containerRef.current?.contains(event.target)) {
        setInputText(selectedOption?.label || '');
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, [selectedOption?.label]);

  const normalizedSearch = inputText.trim().toLowerCase();
  const filtered = allOptions.filter((option) =>
    String(option.label || '').toLowerCase().includes(normalizedSearch),
  );

  const selectOption = (option) => {
    setInputText(option.label);
    setOpen(false);
    setHighlighted(0);

    if (String(option.value) !== String(value)) {
      onChange(option);
    }
  };

  const commitCustom = () => {
    const text = inputText.trim();

    if (!allowCustom || !text) return false;

    const exact = allOptions.find(
      (option) => String(option.label).toLowerCase() === text.toLowerCase(),
    );

    if (exact) {
      selectOption(exact);
      return true;
    }

    const option = {
      value: text,
      label: text,
      isCustom: true,
    };

    setCustomOptions((previous) => [...previous, option]);
    onChange(option);
    setInputText(option.label);
    setOpen(false);

    return true;
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Escape') {
      setInputText(selectedOption?.label || '');
      setOpen(false);
      return;
    }

    if (!open && (event.key === 'ArrowDown' || event.key === 'Enter')) {
      event.preventDefault();
      setOpen(true);
      setHighlighted(0);
      return;
    }

    if (!open) return;

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setHighlighted((current) =>
        Math.min(current + 1, Math.max(filtered.length - 1, 0)),
      );
      return;
    }

    if (event.key === 'ArrowUp') {
      event.preventDefault();
      setHighlighted((current) => Math.max(current - 1, 0));
      return;
    }

    if (event.key === 'Enter') {
      event.preventDefault();

      const exact = allOptions.find(
        (option) =>
          String(option.label).toLowerCase() === inputText.trim().toLowerCase(),
      );

      if (exact) {
        selectOption(exact);
      } else if (allowCustom && inputText.trim()) {
        commitCustom();
      } else if (filtered[highlighted]) {
        selectOption(filtered[highlighted]);
      }
    }
  };

  return (
    <div className="form-field searchable-select" ref={containerRef}>
      {label && (
        <label className="form-field__label" htmlFor={name}>
          {label} {required && <span className="form-field__required">*</span>}
        </label>
      )}

      <div className="searchable-select__control">
        <input
          id={name}
          type="text"
          className={`form-field__input ${error ? 'form-field__input--error' : ''}`}
          value={inputText}
          placeholder={placeholder}
          disabled={disabled}
          onFocus={() => {
            setOpen(true);
            setHighlighted(0);
          }}
          onChange={(event) => {
            setInputText(event.target.value);
            setOpen(true);
            setHighlighted(0);
          }}
          onKeyDown={handleKeyDown}
          autoComplete="off"
        />

        <button
          type="button"
          className="searchable-select__chevron"
          aria-label="Toggle options"
          disabled={disabled}
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => setOpen((current) => !current)}
        >
          ▾
        </button>

        {open && !disabled && (
          <div className="searchable-select__menu">
            {!filtered.length && (
              <div className="searchable-select__empty">
                {allowCustom && inputText.trim()
                  ? `Press Enter to use "${inputText.trim()}"`
                  : emptyMessage}
              </div>
            )}

            {filtered.map((option, index) => (
              <button
                type="button"
                key={`${option.value}-${index}`}
                className={`searchable-select__option ${
                  index === highlighted ? 'searchable-select__option--highlighted' : ''
                } ${
                  String(option.value) === String(value)
                    ? 'searchable-select__option--selected'
                    : ''
                }`}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => selectOption(option)}
                onMouseEnter={() => setHighlighted(index)}
              >
                <span>{option.label}</span>
                {option.meta && (
                  <span className="searchable-select__option-meta">{option.meta}</span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      {error && <span className="form-field__error">{error}</span>}
    </div>
  );
}
