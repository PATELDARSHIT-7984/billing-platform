// Map saved response fields into the existing invoice layout; never reprice a document.
export function documentPdfData(type, data) {
  if (type === 'sale') return data;
  const titles = { purchase: 'PURCHASE BILL', quotation: 'QUOTATION',
    purchaseReturn: 'PURCHASE RETURN', salesReturn: 'SALES RETURN' };
  if (!titles[type]) throw new Error('Unsupported printable document');
  const supplier = type === 'purchase' || type === 'purchaseReturn';
  return {
    bill: {
      ...data,
      document_title: titles[type],
      party_label: supplier ? 'SUPPLIER' : 'CUSTOMER',
      invoice_no: type === 'purchase' ? data.bill_no : type === 'quotation' ? data.quotation_no : data.return_no,
      bill_date: type === 'purchase' ? data.bill_date : type === 'quotation' ? data.quotation_date : data.return_date,
      customer_name: supplier ? data.party_name : data.customer_name,
      state: data.party_state ?? data.state,
      mobile: data.contact_no,
      cgst_amount: data.cgst_total, sgst_amount: data.sgst_total, igst_amount: data.igst_total,
    },
    items: (data.items || []).map((item) => ({
      ...item, rate: item.price, line_total: item.amount,
      gst_percent: data.is_gst === false ? 0 : Number(item.cgst || 0) + Number(item.sgst || 0) + Number(item.igst || 0),
      discount_display: `${item.disc_percent || 0}%`,
    })),
  };
}

export const PDF_MODES = [
  { label: 'With Letterhead', includeLetterhead: true },
  { label: 'Without Letterhead', includeLetterhead: false },
];
