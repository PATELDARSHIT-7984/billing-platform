import Modal from '../components/common/Modal';
import Button from '../components/common/Button';
import {
  formatCurrency,
  formatSignedCurrency,
} from '../utils/calculations';

import './PurchaseDetailModal.css';

export default function SalesReturnDetailModal({
  open,
  loading,
  salesReturn,
  onClose,
}) {
  const items = salesReturn?.items || [];

  return (
    <Modal
      open={open}
      title={
        salesReturn
          ? `Sales Return #${salesReturn.return_no}`
          : 'Sales Return Details'
      }
      onClose={onClose}
      width={900}
      footer={
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      }
    >
      {loading && (
        <div className="purchase-detail__loading">
          Loading sales return...
        </div>
      )}

      {!loading && salesReturn && (
        <div className="purchase-detail">
          <div className="purchase-detail__meta">
            <div>
              <span className="purchase-detail__meta-label">
                Customer
              </span>
              <span className="purchase-detail__meta-value">
                {salesReturn.customer_name || '—'}
              </span>
            </div>

            <div>
              <span className="purchase-detail__meta-label">
                Return Date
              </span>
              <span className="purchase-detail__meta-value">
                {salesReturn.return_date
                  ? new Date(
                      salesReturn.return_date,
                    ).toLocaleDateString('en-IN', {
                      day: '2-digit',
                      month: 'short',
                      year: 'numeric',
                    })
                  : '—'}
              </span>
            </div>

            <div>
              <span className="purchase-detail__meta-label">
                Original Invoice
              </span>
              <span className="purchase-detail__meta-value">
                {salesReturn.original_invoice_no || '—'}
              </span>
            </div>

            <div>
              <span className="purchase-detail__meta-label">
                Return Reason
              </span>
              <span className="purchase-detail__meta-value">
                {salesReturn.return_reason || '—'}
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
                      No returned items.
                    </td>
                  </tr>
                )}

                {items.map((item) => (
                  <tr key={item.id ?? item.sales_return_item_id}>
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
              <span>{formatCurrency(salesReturn.taxable_amount || 0)}</span>
            </div>

            <div className="purchase-detail__summary-row">
              <span>SGST Total</span>
              <span>{formatCurrency(salesReturn.sgst_total || 0)}</span>
            </div>

            <div className="purchase-detail__summary-row">
              <span>CGST Total</span>
              <span>{formatCurrency(salesReturn.cgst_total || 0)}</span>
            </div>

            <div className="purchase-detail__summary-row">
              <span>IGST Total</span>
              <span>{formatCurrency(salesReturn.igst_total || 0)}</span>
            </div>

            <div className="purchase-detail__summary-row purchase-detail__summary-row--muted">
              <span>Round Off</span>
              <span>{formatSignedCurrency(salesReturn.round_off || 0)}</span>
            </div>

            <div className="purchase-detail__grand">
              <span>Grand Total</span>
              <span>{formatCurrency(salesReturn.grand_total || 0)}</span>
            </div>
          </div>

          {salesReturn.remarks && (
            <div className="purchase-detail__summary-row">
              <span>Remarks</span>
              <span>{salesReturn.remarks}</span>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}