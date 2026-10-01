export const company = {
  company_name: 'ABC Electronics', address_line1: '12 Market Road', address_line2: 'Ahmedabad, Gujarat',
  mobile: '9876543210', email: 'accounts@example.com', udyam_no: 'UDYAM-GJ-01-1234567',
  gstin: '24ABCDE1234F1Z5', pan_card: 'ABCDE1234F', bank_account_name: 'ABC Electronics',
  bank_account_no: '123456789012', bank_ifsc: 'TEST0001234', bank_name: 'Example Bank',
  terms_and_conditions: ['Payment due within 30 days.', 'Please quote the document number with payment.'],
  jurisdiction_note: 'Subject to Ahmedabad jurisdiction.',
};
export const invoice = {
  bill: { invoice_no: 'INV-001', bill_date: '2026-09-28', customer_name: 'Rahul Patel',
    address: '21 Shop Road', city: 'Ahmedabad', state: 'Gujarat', mobile: '9876543211',
    taxable_amount: 675, cgst_amount: 60.75, sgst_amount: 60.75, igst_amount: 0,
    round_off: 0.5, grand_total: 797, amount_in_words: 'Rupees Seven Hundred Ninety Seven Only',
    remarks: 'Please handle with care.', due_date: '2026-10-28',
    show_shipping_address_on_bill: true, ship_to: 'Rahul Shop', ship_to_address: 'Warehouse Road',
  },
  items: [{ item_name: 'LED Bulb 9W', hsn_code: '8539', quantity: 5, unit: 'units', rate: 150,
    discount_amount: 75, gst_percent: 18, line_total: 796.5 }],
};
export const quotation = {
  quotation_no: 'QTN-001', quotation_date: '2026-09-28', customer_name: 'Rahul Patel',
  party_name: 'XYZ Suppliers', address: '21 Shop Road', city: 'Ahmedabad', state: 'Gujarat',
  contact_no: '9876543211', taxable_amount: 675, cgst_total: 60.75, sgst_total: 60.75,
  igst_total: 0, round_off: 0.5, grand_total: 797, is_gst: true,
  items: [{ item_name: 'LED Bulb 9W', hsn_code: '8539', quantity: 5, unit: 'units', price: 150,
    disc_percent: 10, cgst: 9, sgst: 9, igst: 0, amount: 796.5 }],
};
