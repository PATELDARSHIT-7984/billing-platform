import Modal from '../components/common/Modal';
import Button from '../components/common/Button';
import { formatCurrency, formatPhoneNumber } from '../utils/calculations';
import './PurchaseDetailModal.css';

export default function QuotationDetailModal({ open, loading, quotation, onClose }) {
  const items = quotation?.items || [];

  return (
    <Modal
      open={open}
      title={quotation ? `Quotation #${quotation.quotation_no}` : 'Quotation Details'}
      onClose={onClose}
      width={900}
      footer={<Button variant="secondary" onClick={onClose}>Close</Button>}
    >
      {loading && <div className="purchase-detail__loading">Loading quotation...</div>}
      {!loading && quotation && (
        <div className="purchase-detail">
          <div className="purchase-detail__meta">
            <div><span className="purchase-detail__meta-label">Customer</span><span className="purchase-detail__meta-value">{quotation.customer_name || '—'}</span></div>
            <div><span className="purchase-detail__meta-label">Quotation Date</span><span className="purchase-detail__meta-value">{new Date(quotation.quotation_date).toLocaleDateString('en-IN')}</span></div>
            <div><span className="purchase-detail__meta-label">Contact</span><span className="purchase-detail__meta-value">{formatPhoneNumber(quotation.contact_no)}</span></div>
            <div><span className="purchase-detail__meta-label">Valid Until</span><span className="purchase-detail__meta-value">{quotation.due_date ? new Date(quotation.due_date).toLocaleDateString('en-IN') : '—'}</span></div>
          </div>
          <div className="purchase-detail__table-wrap">
            <table className="purchase-detail__table">
              <thead><tr><th>Item</th><th>HSN</th><th className="align-right">Qty</th><th>Unit</th><th className="align-right">Price</th><th className="align-right">Amount</th></tr></thead>
              <tbody>
                {!items.length && <tr><td colSpan={6} className="purchase-detail__empty">No quotation items.</td></tr>}
                {items.map((item) => <tr key={item.id}><td>{item.item_name}</td><td>{item.hsn_code || '—'}</td><td className="align-right">{item.quantity}</td><td>{item.unit}</td><td className="align-right">{formatCurrency(item.price)}</td><td className="align-right">{formatCurrency(item.amount)}</td></tr>)}
              </tbody>
            </table>
          </div>
          <div className="purchase-detail__summary">
            <div className="purchase-detail__summary-row"><span>Taxable Amount</span><span>{formatCurrency(quotation.taxable_amount)}</span></div>
            <div className="purchase-detail__summary-row"><span>SGST</span><span>{formatCurrency(quotation.sgst_total)}</span></div>
            <div className="purchase-detail__summary-row"><span>CGST</span><span>{formatCurrency(quotation.cgst_total)}</span></div>
            <div className="purchase-detail__summary-row"><span>IGST</span><span>{formatCurrency(quotation.igst_total)}</span></div>
            <div className="purchase-detail__grand"><span>Grand Total</span><span>{formatCurrency(quotation.grand_total)}</span></div>
          </div>
        </div>
      )}
    </Modal>
  );
}
