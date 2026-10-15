import './FormControlRow.css';

// Labels and messages stay in the owning field, outside this control-only row.
export default function FormControlRow({ children, action }) {
  return action ? <div className="form-control-row">{children}{action}</div> : children;
}
