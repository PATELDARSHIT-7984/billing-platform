import ManagedCreateButton from './ManagedCreateButton';
import { useEffect, useState } from 'react';
import { FormSelect } from './FormField';
import { fetchDoneByList } from '../../services/doneByService';
import { extractErrorMessage } from '../../services/api';
import { doneByOptions } from '../../utils/doneByOptions';

export default function DoneBySelect({ value, savedValue, onChange, onCreate, createdPerson }) {
  const [people, setPeople] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    let cancelled = false;
    fetchDoneByList()
      .then((rows) => { if (!cancelled) setPeople(rows); })
      .catch((reason) => { if (!cancelled) setError(extractErrorMessage(reason)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);
  const available = createdPerson ? [...people.filter((row) => row.id !== createdPerson.id), createdPerson] : people;
  const empty = !available.some((person) => person.is_active);
  const selector = <FormSelect label="Done By" name="done_by" value={value} onChange={onChange}
    options={doneByOptions(available, savedValue)} disabled={loading || empty}
    error={error || (!loading && empty ? 'No active Done By available. Add one from Done By Management.' : '')} />;
  return onCreate ? <div className="gt-with-action">{selector}<ManagedCreateButton entity="doneBy" onClick={onCreate} /></div> : selector;
}
