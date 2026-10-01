import PdfDownloadActions from '../components/common/PdfDownloadActions';
import Modal from '../components/common/Modal';
import Button from '../components/common/Button';
import { formatCurrency } from '../utils/calculations';
import './PurchaseDetailModal.css';
import '../styles/SalesEntry.css';

export default function BillDetailModal({ open, loading, billDetail, onClose }) {
  const bill = billDetail?.bill;
  const items = billDetail?.items || [];
  const isInterstate = (bill?.igst_amount || 0) > 0;

  return (
    <Modal
      open={open}
      title={bill ? `Invoice #${bill.invoice_no}` : 'Sale Details'}
      onClose={onClose}
      width={860}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
          {bill && (
            <PdfDownloadActions type="sale" loadDetail={() => billDetail} />
          )}
        </>
      }
    >
      {loading && <div className="purchase-detail__loading">Loading sale...</div>}

      {!loading && bill && (
        <div className="purchase-detail">
          <div className="purchase-detail__meta">
            <div>
              <span className="purchase-detail__meta-label">Customer</span>
              <span className="purchase-detail__meta-value">{bill.customer_name || '—'}</span>
            </div>
            <div>
              <span className="purchase-detail__meta-label">Bill Date</span>
              <span className="purchase-detail__meta-value">
                {new Date(bill.bill_date).toLocaleDateString('en-IN', {
                  day: '2-digit',
                  month: 'short',
                  year: 'numeric',
                })}
              </span>
            </div>
            <div>
              <span className="purchase-detail__meta-label">Mobile</span>
              <span className="purchase-detail__meta-value">{bill.mobile || '—'}</span>
            </div>
            {bill.buyer_gstin && (
              <div>
                <span className="purchase-detail__meta-label">Customer GSTIN</span>
                <span className="purchase-detail__meta-value">{bill.buyer_gstin}</span>
              </div>
            )}
            <div>
              <span className="purchase-detail__meta-label">Supply Type</span>
              <span className="purchase-detail__meta-value">{isInterstate ? 'Interstate (IGST)' : 'Intrastate (CGST+SGST)'}</span>
            </div>
          </div>

          <div className="purchase-detail__table-wrap">
            <table className="purchase-detail__table">
              <thead>
                <tr>
                  <th>Item Name</th>
                  <th>HSN</th>
                  <th className="align-right">Qty</th>
                  <th>Unit</th>
                  <th className="align-right">Rate</th>
                  <th className="align-right">GST %</th>
                  <th className="align-right">Line Total</th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 && (
                  <tr>
                    <td colSpan={7} className="purchase-detail__empty">
                      No items on this bill.
                    </td>
                  </tr>
                )}
                {items.map((item) => (
                  <tr key={item.bill_item_id}>
                    <td>{item.item_name}</td>
                    <td>{item.hsn_code || '—'}</td>
                    <td className="align-right">{item.quantity}</td>
                    <td>{item.unit}</td>
                    <td className="align-right">{formatCurrency(item.rate)}</td>
                    <td className="align-right">{item.gst_percent}%</td>
                    <td className="align-right">{formatCurrency(item.line_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="purchase-detail__summary">
            <div className="purchase-detail__summary-row">
              <span>Subtotal (Taxable Amount)</span>
              <span>{formatCurrency(bill.taxable_amount)}</span>
            </div>
            {isInterstate ? (
              <div className="purchase-detail__summary-row">
                <span>IGST</span>
                <span>{formatCurrency(bill.igst_amount)}</span>
              </div>
            ) : (
              <>
                <div className="purchase-detail__summary-row">
                  <span>CGST</span>
                  <span>{formatCurrency(bill.cgst_amount)}</span>
                </div>
                <div className="purchase-detail__summary-row">
                  <span>SGST</span>
                  <span>{formatCurrency(bill.sgst_amount)}</span>
                </div>
              </>
            )}
            <div className="purchase-detail__grand">
              <span>Grand Total</span>
              <span>{formatCurrency(bill.grand_total)}</span>
            </div>
          </div>

          {bill.amount_in_words && (
            <p className="bill-summary__words" style={{ textAlign: 'right', marginTop: 8 }}>
              {bill.amount_in_words}
            </p>
          )}

          {bill.remarks && (
            <p className="purchase-detail__empty" style={{ textAlign: 'left', padding: '8px 0 0' }}>
              <strong>Remarks:</strong> {bill.remarks}
            </p>
          )}
        </div>
      )}
    </Modal>
  );
}
