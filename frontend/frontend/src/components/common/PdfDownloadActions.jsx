import { useState } from 'react';
import { useCompany } from '../../context/CompanyContext';
import { useToast } from '../../context/ToastContext';
import { extractErrorMessage } from '../../services/api';
import { downloadDocumentPDF } from '../../utils/pdfGenerator';
import { PDF_MODES } from '../../utils/documentPdfData';
import Button from './Button';

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
  return <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }} onClick={(event) => event.stopPropagation()}>
    {PDF_MODES.map(({ label, includeLetterhead }) => (
      <Button key={label} size="sm" variant="secondary"
        disabled={busy || loading} title={`Download PDF ${label.toLowerCase()}`}
        onClick={() => download(includeLetterhead)}>
        PDF {label}
      </Button>
    ))}
  </div>;
}
