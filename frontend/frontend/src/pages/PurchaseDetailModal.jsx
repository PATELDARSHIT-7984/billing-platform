import Modal from '../components/common/Modal';
import Button from '../components/common/Button';
import {
  formatCurrency,
  formatSignedCurrency,
} from '../utils/calculations';

import './PurchaseDetailModal.css';

export default function PurchaseReturnDetailModal({
  open,
  loading,
  purchaseReturn,
  onClose,
}) {
  const items = purchaseReturn?.items || [];

  return (
    <Modal
      open={open}
      title={
        purchaseReturn
          ? `Purchase Return #${purchaseReturn.return_no}`
          : 'Purchase Return Details'
      }
      onClose={onClose}
      width={860}
      footer={
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      }
    >
      {loading && (
        <div className="purchase-detail__loading">
          Loading purchase return...
        </div>
      )}

      {!loading && purchaseReturn && (
        <div className="purchase-detail">
          <div className="purchase-detail__meta">
            <div>
              <span className="purchase-detail__meta-label">Supplier</span>
              <span className="purchase-detail__meta-value">
                {purchaseReturn.party_name || '—'}
              </span>
            </div>

            <div>
              <span className="purchase-detail__meta-label">Return Date</span>
              <span className="purchase-detail__meta-value">
                {purchaseReturn.return_date
                  ? new Date(
                      purchaseReturn.return_date,
                    ).toLocaleDateString('en-IN', {
                      day: '2-digit',
                      month: 'short',
                      year: 'numeric',
                    })
                  : '—'}
              </span>
            </div>

            <div>
              <span className="purchase-detail__meta-label">Original Bill</span>
              <span className="purchase-detail__meta-value">
                {purchaseReturn.original_bill_no || '—'}
              </span>
            </div>

            <div>
              <span className="purchase-detail__meta-label">Return Reason</span>
              <span className="purchase-detail__meta-value">
                {purchaseReturn.return_reason || '—'}
              </span>
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
                  <th className="align-right">Price</th>
                  <th className="align-right">Amount</th>
                </tr>
              </thead>

              <tbody>
                {!items.length && (
                  <tr>
                    <td colSpan={6} className="purchase-detail__empty">
                      No items on this purchase return.
                    </td>
                  </tr>
                )}

                {items.map((item) => (
                  <tr key={item.id ?? item.purchase_return_item_id}>
                    <td>{item.item_name}</td>
                    <td>{item.hsn_code || '—'}</td>
                    <td className="align-right">{item.quantity}</td>
                    <td>{item.unit || '—'}</td>
                    <td className="align-right">
                      {formatCurrency(item.price || 0)}
                    </td>
                    <td className="align-right">
                      {formatCurrency(item.amount || 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="purchase-detail__summary">
            <div className="purchase-detail__summary-row">
              <span>Taxable Amount</span>
              <span>{formatCurrency(purchaseReturn.taxable_amount || 0)}</span>
            </div>

            <div className="purchase-detail__summary-row">
              <span>SGST Total</span>
              <span>{formatCurrency(purchaseReturn.sgst_total || 0)}</span>
            </div>

            <div className="purchase-detail__summary-row">
              <span>CGST Total</span>
              <span>{formatCurrency(purchaseReturn.cgst_total || 0)}</span>
            </div>

            <div className="purchase-detail__summary-row">
              <span>IGST Total</span>
              <span>{formatCurrency(purchaseReturn.igst_total || 0)}</span>
            </div>

            <div className="purchase-detail__summary-row purchase-detail__summary-row--muted">
              <span>Round Off</span>
              <span>{formatSignedCurrency(purchaseReturn.round_off || 0)}</span>
            </div>

            <div className="purchase-detail__grand">
              <span>Grand Total</span>
              <span>{formatCurrency(purchaseReturn.grand_total || 0)}</span>
            </div>
          </div>

          {purchaseReturn.remarks && (
            <p
              className="purchase-detail__empty"
              style={{ textAlign: 'left', padding: '8px 0 0' }}
            >
              <strong>Remarks:</strong> {purchaseReturn.remarks}
            </p>
          )}
        </div>
      )}
    </Modal>
  );
}
