import { useState, useEffect } from 'react';
import Modal from '../components/common/Modal';
import Button from '../components/common/Button';
import Badge from '../components/common/Badge';
import { useToast } from '../context/ToastContext';
import { fetchAccountSettlement, submitContraOffset } from '../services/unifiedAccountService';
import { extractErrorMessage } from '../services/api';
import './AccountSettlementModal.css';

export default function AccountSettlementModal({ open, account, onClose, onSettlementApplied }) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [settlement, setSettlement] = useState(null);
  const [offsetAmount, setOffsetAmount] = useState('');
  const [offsetRemark, setOffsetRemark] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const loadSettlementData = async () => {
    if (!account?.id) return;
    setLoading(true);
    try {
      const data = await fetchAccountSettlement(account.id);
      setSettlement(data);
      const rec = Number(data.total_receivable || 0);
      const pay = Number(data.total_payable || 0);
      const maxContra = Math.min(rec, pay);
      if (maxContra > 0) {
        setOffsetAmount(maxContra.toFixed(2));
        setOffsetRemark('Mutual contra settlement');
      } else {
        setOffsetAmount('');
        setOffsetRemark('');
      }
    } catch (err) {
      toast.error(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open && account) {
      loadSettlementData();
    } else {
      setSettlement(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, account]);

  const receivable = Number(settlement?.total_receivable || 0);
  const payable = Number(settlement?.total_payable || 0);
  const maxContra = Math.min(receivable, payable);
  const canContra = maxContra > 0;

  const handleApplyContra = async (e) => {
    e.preventDefault();
    const amountNum = Number(offsetAmount);
    if (!amountNum || amountNum <= 0) {
      toast.error('Please enter a valid contra offset amount greater than 0.');
      return;
    }
    if (amountNum > maxContra) {
      toast.error(`Contra offset amount cannot exceed maximum allowable ₹${maxContra.toFixed(2)}.`);
      return;
    }

    const debitRoleObj = (settlement?.roles || []).find(
      (r) => (r.current_balance_type === 'Debit' || r.balance_type === 'Debit') && Number(r.current_balance || r.balance || 0) > 0
    );
    const creditRoleObj = (settlement?.roles || []).find(
      (r) => (r.current_balance_type === 'Credit' || r.balance_type === 'Credit') && Number(r.current_balance || r.balance || 0) > 0
    );

    if (!debitRoleObj || !creditRoleObj) {
      toast.error('Both a Debit (Receivable) role and Credit (Payable) role are required for contra offset.');
      return;
    }

    setSubmitting(true);
    try {
      await submitContraOffset(account.id, {
        receivable_role: debitRoleObj.role,
        payable_role: creditRoleObj.role,
        amount: amountNum,
        remark: offsetRemark || undefined,
      });
      toast.success(`Contra offset of ₹${amountNum.toFixed(2)} applied successfully.`);
      await loadSettlementData();
      if (onSettlementApplied) {
        onSettlementApplied();
      }
    } catch (err) {
      toast.error(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={open}
      title={`Account Settlement — ${account?.account_name || account?.name || ''}`}
      onClose={onClose}
      width={720}
      footer={
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      }
    >
      <div className="settlement-modal">
        {loading && (
          <div className="settlement-loading">
            <div className="settlement-spinner" />
            <span>Calculating net consolidated settlement...</span>
          </div>
        )}

        {!loading && settlement && (
          <>
            {/* Account Identifier Badge */}
            <div className="settlement-header-bar">
              <span className="settlement-account-code">{settlement.account_code}</span>
              <span className="settlement-account-name">{settlement.account_name}</span>
            </div>

            {/* KPI Cards */}
            <div className="settlement-kpi-grid">
              <div className="settlement-kpi settlement-kpi--receivable">
                <span className="settlement-kpi__label">Total Receivable (Dr)</span>
                <span className="settlement-kpi__value">
                  ₹{Number(settlement.total_receivable || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </span>
                <span className="settlement-kpi__sub">Amount customer owes you</span>
              </div>

              <div className="settlement-kpi settlement-kpi--payable">
                <span className="settlement-kpi__label">Total Payable (Cr)</span>
                <span className="settlement-kpi__value">
                  ₹{Number(settlement.total_payable || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </span>
                <span className="settlement-kpi__sub">Amount you owe supplier</span>
              </div>

              <div className="settlement-kpi settlement-kpi--net">
                <span className="settlement-kpi__label">Net Position</span>
                <span className="settlement-kpi__value">
                  ₹{Number(settlement.net_amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </span>
                <span className="settlement-kpi__badge">
                  <Badge
                    tone={
                      settlement.settlement_status === 'RECEIVABLE'
                        ? 'green'
                        : settlement.settlement_status === 'PAYABLE'
                        ? 'amber'
                        : 'gray'
                    }
                  >
                    {settlement.settlement_status === 'RECEIVABLE'
                      ? 'Net Receivable'
                      : settlement.settlement_status === 'PAYABLE'
                      ? 'Net Payable'
                      : 'Fully Settled'}
                  </Badge>
                </span>
              </div>
            </div>

            {settlement.summary_text && (
              <div className="settlement-summary-callout">
                {settlement.summary_text}
              </div>
            )}

            {/* Role Breakdown Table */}
            <div className="settlement-section">
              <div className="settlement-section__title">Role Breakdown</div>
              <div className="settlement-table-wrap">
                <table className="settlement-table">
                  <thead>
                    <tr>
                      <th>Role</th>
                      <th>Ledger Balance</th>
                      <th>Direction</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(settlement.roles || []).map((r, i) => (
                      <tr key={i}>
                        <td className="settlement-role-name">
                          <span className={`settlement-role-pill settlement-role-pill--${(r.role || '').toLowerCase()}`}>
                            {r.role}
                          </span>
                        </td>
                        <td className="settlement-num">
                          ₹{Number(r.current_balance || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </td>
                        <td>
                          {r.current_balance_type ? (
                            <span className={`direction-tag direction-tag--${(r.current_balance_type || '').toLowerCase()}`}>
                              {r.current_balance_type}
                            </span>
                          ) : (
                            <span className="direction-tag">Nil</span>
                          )}
                        </td>
                        <td>
                          <Badge
                            tone={
                              r.direction_role === 'RECEIVABLE'
                                ? 'green'
                                : r.direction_role === 'PAYABLE'
                                ? 'amber'
                                : 'gray'
                            }
                          >
                            {r.direction_role || 'Settled'}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Contra Offset Section */}
            {canContra && (
              <div className="settlement-contra-card">
                <div className="settlement-contra-header">
                  <span className="settlement-contra-icon">⚖️</span>
                  <div>
                    <div className="settlement-contra-title">One-Click Contra Offset</div>
                    <div className="settlement-contra-desc">
                      Settle mutual receivable and payable balances directly without bank transactions.
                    </div>
                  </div>
                </div>

                <form onSubmit={handleApplyContra} className="settlement-contra-form">
                  <div className="settlement-contra-inputs">
                    <div className="settlement-field">
                      <label>Offset Amount (₹)</label>
                      <div className="settlement-amount-input-wrap">
                        <input
                          type="number"
                          step="0.01"
                          max={maxContra}
                          value={offsetAmount}
                          onChange={(e) => setOffsetAmount(e.target.value)}
                          placeholder="Amount"
                          required
                        />
                        <button
                          type="button"
                          className="settlement-max-btn"
                          onClick={() => setOffsetAmount(maxContra.toFixed(2))}
                        >
                          Max (₹{maxContra.toFixed(2)})
                        </button>
                      </div>
                    </div>

                    <div className="settlement-field">
                      <label>Contra Remark</label>
                      <input
                        type="text"
                        value={offsetRemark}
                        onChange={(e) => setOffsetRemark(e.target.value)}
                        placeholder="e.g. Mutual contra offset"
                      />
                    </div>
                  </div>

                  <div className="settlement-contra-action">
                    <Button
                      type="submit"
                      variant="primary"
                      disabled={submitting || !Number(offsetAmount) || Number(offsetAmount) <= 0}
                    >
                      {submitting ? 'Applying Offset...' : `Apply Contra Offset (₹${Number(offsetAmount || 0).toFixed(2)})`}
                    </Button>
                  </div>
                </form>
              </div>
            )}

            {/* Settled / One-Sided Status Banner */}
            {!canContra && settlement && (
              <div className="settlement-status-banner">
                {settlement.settlement_status === 'SETTLED' ? (
                  <>
                    <span className="settlement-status-icon">✅</span>
                    <div>
                      <div className="settlement-status-title">Balances Fully Settled</div>
                      <div className="settlement-status-desc">
                        Both receivable and payable are in equilibrium. No contra offset is needed.
                      </div>
                    </div>
                  </>
                ) : (
                  <>
                    <span className="settlement-status-icon">💡</span>
                    <div>
                      <div className="settlement-status-title">Single Direction Balance</div>
                      <div className="settlement-status-desc">
                        Only {settlement.settlement_status === 'RECEIVABLE' ? 'Receivable (Debit)' : 'Payable (Credit)'} balance
                        remaining — no mutual offset is required. Edit account balances to add an opposing role for settlement.
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}

