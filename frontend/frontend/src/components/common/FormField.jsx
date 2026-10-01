import './FormField.css';

export function FormInput({
  label,
  name,
  value,
  onChange,
  type = 'text',
  placeholder = '',
  required = false,
  error = '',
  disabled = false,
  maxLength,
  autoFocus = false,
}) {
  return (
    <div className="form-field">
      {label && (
        <label className="form-field__label" htmlFor={name}>
          {label} {required && <span className="form-field__required">*</span>}
        </label>
      )}
      <input
        id={name}
        name={name}
        type={type}
        value={value ?? ''}
        placeholder={placeholder}
        disabled={disabled}
        maxLength={maxLength}
        autoFocus={autoFocus}
        onChange={(e) => onChange(e.target.value)}
        className={`form-field__input ${error ? 'form-field__input--error' : ''}`}
      />
      {error && <span className="form-field__error">{error}</span>}
    </div>
  );
}

export function FormSelect({ label, name, value, onChange, options, required = false, error = '', disabled = false }) {
  return (
    <div className="form-field">
      {label && (
        <label className="form-field__label" htmlFor={name}>
          {label} {required && <span className="form-field__required">*</span>}
        </label>
      )}
      <select
        id={name}
        name={name}
        value={value ?? ''}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className={`form-field__input form-field__select ${error ? 'form-field__input--error' : ''}`}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value} disabled={opt.disabled}>
            {opt.label}
          </option>
        ))}
      </select>
      {error && <span className="form-field__error">{error}</span>}
    </div>
  );
}

export function FormTextarea({ label, name, value, onChange, placeholder = '', required = false, error = '', rows = 3, disabled = false }) {
  return (
    <div className="form-field">
      {label && (
        <label className="form-field__label" htmlFor={name}>
          {label} {required && <span className="form-field__required">*</span>}
        </label>
      )}
      <textarea
        id={name}
        name={name}
        rows={rows}
        value={value ?? ''}
        placeholder={placeholder}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className={`form-field__input form-field__textarea ${error ? 'form-field__input--error' : ''}`}
      />
      {error && <span className="form-field__error">{error}</span>}
    </div>
  );
}

export function FormRow({ children }) {
  return <div className="form-row">{children}</div>;
}

export function FormCheckbox({ label, name, checked, onChange, disabled = false }) {
  return (
    <label className={`form-checkbox ${disabled ? 'form-checkbox--disabled' : ''}`} htmlFor={name}>
      <input
        id={name}
        name={name}
        type="checkbox"
        checked={!!checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="form-checkbox__box" />
      <span className="form-checkbox__label">{label}</span>
    </label>
  );
}
