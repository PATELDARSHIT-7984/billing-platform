import api from './api';

const ACCOUNTS_ENDPOINT = '/accounts/';

export async function fetchUnifiedAccounts({ search = '', role, accountType, page = 1, pageSize = 10 } = {}) {
  const effectiveRole = (role && role !== 'ALL') ? role : (accountType && accountType !== 'ALL' ? accountType : undefined);
  const params = {
    search: search?.trim() || undefined,
    role: effectiveRole || undefined,
    page,
    page_size: pageSize,
  };
  const res = await api.get(ACCOUNTS_ENDPOINT, { params });
  return res.data;
}

export async function fetchUnifiedAccountById(id) {
  const res = await api.get(`${ACCOUNTS_ENDPOINT}${id}`);
  return res.data;
}

export async function createUnifiedAccount(payload) {
  const res = await api.post(ACCOUNTS_ENDPOINT, payload);
  return res.data;
}

export async function updateUnifiedAccount(id, payload) {
  const res = await api.put(`${ACCOUNTS_ENDPOINT}${id}`, payload);
  return res.data;
}

export async function deleteUnifiedAccount(id) {
  const res = await api.delete(`${ACCOUNTS_ENDPOINT}${id}`);
  return res.data;
}

export async function fetchAccountSettlement(id) {
  const res = await api.get(`${ACCOUNTS_ENDPOINT}${id}/settlement`);
  return res.data;
}

export async function submitContraOffset(id, { receivable_role, payable_role, amount, remark }) {
  const res = await api.post(`${ACCOUNTS_ENDPOINT}${id}/contra-offset`, {
    receivable_role,
    payable_role,
    amount: Number(amount),
    remark: remark?.trim() || undefined,
  });
  return res.data;
}

export async function addAccountRole(id, rolePayload) {
  const res = await api.post(`${ACCOUNTS_ENDPOINT}${id}/roles`, rolePayload);
  return res.data;
}

export async function saveUnifiedAccount(form, existing = null) {
  const isEdit = Boolean(existing && existing.id);

  if (!isEdit) {
    const rolesInput = (form.roles && form.roles.length > 0)
      ? form.roles.map((r) => {
          const bal = Number(r.opening_balance || 0);
          return {
            role: r.role,
            opening_balance: bal === 0 ? '0.00' : String(r.opening_balance).trim(),
            balance_type: bal > 0 ? (r.balance_type || 'Credit') : null,
            opening_remark: r.opening_remark?.trim() || null,
          };
        })
      : [
          {
            role: form.accountType || 'CUSTOMER',
            opening_balance: Number(form.opening_balance || 0) === 0 ? '0.00' : String(form.opening_balance).trim(),
            balance_type: Number(form.opening_balance || 0) > 0 ? (form.balance_type || 'Credit') : null,
            opening_remark: form.opening_remark?.trim() || null,
          },
        ];

    const createPayload = {
      account_name: form.name.trim(),
      country_code: form.country_code || '+91',
      mobile: form.mobile?.trim() || null,
      address: form.address?.trim() || null,
      city: form.city?.trim() || null,
      state: form.state || null,
      gstin: form.gstin?.trim().toUpperCase() || null,
      pan_card: form.pan_card?.trim().toUpperCase() || null,
      remarks: form.remarks?.trim() || null,
      roles: rolesInput,
    };
    const created = await createUnifiedAccount(createPayload);
    const hasCustomerRole = created.roles?.some((r) => r.role === 'CUSTOMER');
    return {
      ...created,
      name: created.account_name,
      customer_name: created.account_name,
      source: hasCustomerRole ? 'customer' : 'party',
      accountType: created.roles?.[0]?.role || 'SUPPLIER',
    };
  }

  // Edit existing account
  const updatePayload = {
    account_name: form.name.trim(),
    country_code: form.country_code || '+91',
    mobile: form.mobile?.trim() || null,
    address: form.address?.trim() || null,
    city: form.city?.trim() || null,
    state: form.state || null,
    gstin: form.gstin?.trim().toUpperCase() || null,
    pan_card: form.pan_card?.trim().toUpperCase() || null,
    remarks: form.remarks?.trim() || null,
    roles: (form.roles || []).map((r) => {
      const bal = Number(r.opening_balance || 0);
      return {
        role: r.role,
        opening_balance: bal === 0 ? '0.00' : String(r.opening_balance).trim(),
        balance_type: bal > 0 ? (r.balance_type || 'Credit') : null,
        opening_remark: r.opening_remark?.trim() || null,
      };
    }),
  };
  let updated = await updateUnifiedAccount(existing.id, updatePayload);

  const hasCustomerRole = updated.roles?.some((r) => r.role === 'CUSTOMER');
  return {
    ...updated,
    name: updated.account_name,
    customer_name: updated.account_name,
    source: hasCustomerRole ? 'customer' : 'party',
    accountType: updated.roles?.[0]?.role || 'SUPPLIER',
  };
}

