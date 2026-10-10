// Mirrors CustomerCreate/CustomerUpdate validation from customer_schema.py
export function validateCustomer(form) {
  const errors = {};

  const trimmedName = form.customer_name.trim();
  if (!trimmedName) errors.customer_name = 'Customer name is required.';
  else if (trimmedName.length < 2 || trimmedName.length > 100) {
    errors.customer_name = 'Name must be between 2 and 100 characters.';
  }

  if (!/^[6-9]\d{9}$/.test(form.mobile.trim())) {
    errors.mobile = 'Enter a valid 10-digit mobile number (starting 6-9).';
  }

  if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) {
    errors.email = 'Enter a valid email address.';
  }

  // address/city/state are required — Bill snapshots these onto every
  // invoice as NOT NULL columns, so an incomplete customer would crash
  // Sales Entry at billing time rather than here.
  if (!form.address.trim()) errors.address = 'Address is required (needed to print invoices).';
  if (!form.city.trim()) errors.city = 'City is required.';
  if (!form.state.trim()) errors.state = 'State is required.';

  if (form.gstin && !/^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1}$/.test(form.gstin.trim().toUpperCase())) {
    errors.gstin = 'Invalid GSTIN format.';
  }

  if (form.pan_card && form.pan_card.trim().length !== 10) {
    errors.pan_card = 'PAN must be exactly 10 characters.';
  }

  if (form.state_code && form.state_code.trim().length !== 2) {
    errors.state_code = 'State code must be exactly 2 digits (e.g. 24 for Gujarat).';
  }

  return errors;
}

