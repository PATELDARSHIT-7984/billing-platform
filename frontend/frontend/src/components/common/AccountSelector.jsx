import { useEffect, useState } from 'react';
import SearchableSelect from './SearchableSelect';
import { FormSelect } from './FormField';
import { accountTypesForSource, fetchAccounts, fetchAccountRecord, normalizeAccountRecord } from '../../services/accountService';
import { extractErrorMessage } from '../../services/api';
import './AccountSelector.css';

export default function AccountSelector({ domain, source = domain || 'party', value, record, defaultType,
  onChange, name = 'account', required = false, error = '', disabled = false }) {
  const types = accountTypesForSource(domain);
  const [type, setType] = useState(defaultType || (domain === 'customer' ? 'CUSTOMER' : 'SUPPLIER'));
  const [search, setSearch] = useState('');
  const [resolved, setResolved] = useState(null);
  const [result, setResult] = useState({ key: '', items: [] });
  const [lookupError, setLookupError] = useState('');
  const selected = value && String(record?.id) === String(value) ? normalizeAccountRecord(source, record)
    : value && resolved?.source === source && String(resolved?.id) === String(value) ? resolved : null;
  const selectedType = selected?.accountType;
  const effectiveType = selectedType || (types.some((entry) => entry.value === type) ? type : types[0].value);
  const key = JSON.stringify([effectiveType, search]);
  const initializing = Boolean(value && !selected && !lookupError);

  useEffect(() => {
    if (!value || String(record?.id) === String(value)
      || (resolved?.source === source && String(resolved?.id) === String(value))) return;
    let cancelled = false;
    fetchAccountRecord(source, value, {}).then((row) => {
      if (!cancelled) { setResolved(row); setLookupError(''); }
    }).catch((err) => { if (!cancelled) setLookupError(extractErrorMessage(err)); });
    return () => { cancelled = true; };
  }, [value, source, record, resolved]);

  useEffect(() => {
    if (initializing || disabled) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      fetchAccounts({ accountType: effectiveType, search, page: 1, pageSize: 20 })
        .then((page) => { if (!cancelled) setResult({ key, items: page.items }); })
        .catch((err) => { if (!cancelled) setResult({ key, items: [], error: extractErrorMessage(err) }); });
    }, 350);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [effectiveType, search, key, initializing, disabled]);

  const rows = result.key === key ? result.items : [];
  const visibleRows = selected && !search && !rows.some((row) => row.id === selected.id) ? [selected, ...rows] : rows;
  const options = visibleRows.map((row) => ({ value: row.id, label: row.name,
    meta: row.city || row.mobile || '', source: row.source, accountType: row.accountType, record: row }));
  // Historical legacy Party Customers are shown, never silently converted.
  const typeOptions = selected && !selectedType ? [{ value: 'legacy', label: selected.unavailable ? 'Saved Party' : 'Legacy Party' }, ...types] : types;

  return <div className="account-selector">
    <FormSelect label="Account Type" name={`${name}_type`} options={typeOptions}
      value={selected && !selectedType ? 'legacy' : effectiveType} disabled={disabled || initializing}
      onChange={(next) => {
        setType(next); setSearch(''); setResolved(null); setLookupError('');
        onChange(null, next);
      }} />
    <SearchableSelect key={effectiveType} label={required ? 'Account' : 'Account (optional)'} name={name}
      value={value} selectedLabel={selected?.name || ''} options={required ? options : [{ value: '', label: 'None' }, ...options]}
      required={required} disabled={disabled || initializing} placeholder="Search accounts..."
      error={error || lookupError || (selected?.unavailable ? 'Saved account is unavailable for new selections.' : '') || (result.key === key ? result.error : '')}
      emptyMessage={result.key !== key ? 'Loading accounts...' : 'No matching accounts.'}
      onSearchChange={setSearch} onChange={(option) => {
        setType(option.accountType || effectiveType); setSearch('');
        setResolved(option.record || null); onChange(option.value === '' ? null : option);
      }} />
  </div>;
}
