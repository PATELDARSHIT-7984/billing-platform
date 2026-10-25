import { useState } from 'react';
import { useCompany } from '../../context/CompanyContext';
import { useToast } from '../../context/ToastContext';
import { extractErrorMessage } from '../../services/api';
import { downloadDocumentPDF } from '../../utils/pdfGenerator';
import { PDF_MODES } from '../../utils/documentPdfData';
import './PdfDownloadActions.css';

export default function PdfDownloadActions({ type, loadDetail }) {
  const { company, loading } = useCompany();
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  async function download(includeLetterhead) {
    setBusy(true);
    try {
      const detail = await loadDetail();
      downloadDocumentPDF(type, detail, company, { includeLetterhead });
    } catch (error) {
      toast.error(extractErrorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="pdf-download-actions" onClick={(event) => event.stopPropagation()}>
      {PDF_MODES.map(({ label, includeLetterhead }) => (
        <button
          key={label}
          type="button"
          className={`pdf-action-btn ${includeLetterhead ? 'pdf-action-btn--primary' : 'pdf-action-btn--secondary'}`}
          disabled={busy || loading}
          title={`Download PDF ${label.toLowerCase()}`}
          onClick={() => download(includeLetterhead)}
        >
          {includeLetterhead && (
            <svg
              className="pdf-action-btn__icon"
              viewBox="0 0 24 24"
              width="13"
              height="13"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
            </svg>
          )}
          <span>{busy ? 'Exporting...' : includeLetterhead ? 'Letterhead' : 'Plain'}</span>
        </button>
      ))}
    </div>
  );
}
