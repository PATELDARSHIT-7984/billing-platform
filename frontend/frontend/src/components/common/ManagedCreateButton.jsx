import { MANAGED_ENTITIES } from '../../utils/draftStorage';

export default function ManagedCreateButton({ entity, onClick, disabled = false }) {
  const label = `Add new ${MANAGED_ENTITIES[entity].label}`;
  return <button type="button" className="gt-plus" onClick={onClick} disabled={disabled}
    title={label} aria-label={label}>+</button>;
}
