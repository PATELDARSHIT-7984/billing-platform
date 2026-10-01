export function doneByOptions(people, savedValue = '') {
  const options = people.filter((person) => person.is_active).map((person) => ({
    value: person.name, label: person.name,
  }));
  if (savedValue && !options.some((option) => option.value === savedValue)) {
    options.unshift({ value: savedValue, label: `${savedValue} (saved)`, disabled: true });
  }
  return [{ value: '', label: 'Select Done By' }, ...options];
}
