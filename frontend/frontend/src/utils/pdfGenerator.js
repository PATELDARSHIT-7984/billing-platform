import { jsPDF } from 'jspdf';
import { documentPdfData } from './documentPdfData.js';

// ---- App design tokens, translated to RGB for jsPDF (mirrors variables.css) ----
const COLOR_PRIMARY = [22, 87, 214]; // --color-primary
const COLOR_NAVY = [11, 36, 71]; // --color-sidebar-bg
const COLOR_TEXT = [27, 36, 55]; // --color-text-primary
const COLOR_MUTED = [89, 98, 122]; // --color-text-secondary
const COLOR_BORDER = [210, 217, 230];
const COLOR_HEADER_BG = [232, 240, 254]; // --color-primary-light

const PAGE_WIDTH = 210;
const PAGE_HEIGHT = 297;
const MARGIN = 12;
const CONTENT_WIDTH = PAGE_WIDTH - MARGIN * 2;
export const LETTERHEAD_HEIGHT = 40; // First page only, including pre-printed paper.

function formatINR(value) {
  const num = Number(value) || 0;
  return `Rs. ${num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatDate(dateStr) {
  if (!dateStr) return '-';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

/**
 * billDetail: { bill: BillResponse, items: BillItemResponse[] }
 * company: CompanyProfileResponse from /company-profile (see CompanyContext)
 */
export function generateInvoicePDF(billDetail, company = {}, { includeLetterhead = true } = {}) {
  company = company || {};
  const { bill, items } = billDetail;
  const isInterstate = (bill.igst_amount || 0) > 0;

  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  let y = MARGIN;

  function ensureRoom(height) {
    if (y + height > PAGE_HEIGHT - MARGIN) {
      doc.addPage();
      y = MARGIN;
    }
  }

  function writeLines(text, width = CONTENT_WIDTH, x = MARGIN, spacing = 4) {
    const lines = doc.splitTextToSize(String(text || ''), width);
    lines.forEach((line) => {
      ensureRoom(spacing + 2);
      doc.text(line, x, y + spacing);
      y += spacing;
    });
  }

  // ---------------- HEADER: Company + Invoice meta ----------------
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(19);
  doc.setTextColor(...COLOR_NAVY);
  if (includeLetterhead) {
  doc.text(doc.splitTextToSize(company.company_name || '', CONTENT_WIDTH).slice(0, 2), MARGIN, y + 6);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8.5);
  doc.setTextColor(...COLOR_MUTED);
  doc.text(doc.splitTextToSize([company.address_line1, company.address_line2].filter(Boolean).join(', '), CONTENT_WIDTH).slice(0, 2), MARGIN, y + 17);
  if (company.udyam_no) {
    doc.text(company.udyam_no, MARGIN, y + 26);
  }
  doc.text(doc.splitTextToSize([company.mobile, company.email].filter(Boolean).join(' | '), CONTENT_WIDTH).slice(0, 2), MARGIN, y + 31);
  }
  y += LETTERHEAD_HEIGHT;

  // Right-aligned invoice meta box
  const metaX = PAGE_WIDTH - MARGIN;
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(13);
  doc.setTextColor(...COLOR_PRIMARY);
  doc.text(bill.document_title || 'SALES INVOICE', metaX, y + 6, { align: 'right' });

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(9);
  doc.setTextColor(...COLOR_TEXT);
  doc.text(`${bill.document_title ? 'Document' : 'Invoice'} No.: ${bill.invoice_no}`, metaX, y + 12, { align: 'right' });
  doc.text(`Date: ${formatDate(bill.bill_date)}`, metaX, y + 17, { align: 'right' });
  doc.setTextColor(...COLOR_MUTED);
  doc.setFontSize(8);
  doc.text(isInterstate ? 'Supply Type: Interstate (IGST)' : 'Supply Type: Intrastate (CGST + SGST)', metaX, y + 22, { align: 'right' });

  y += 27;
  doc.setDrawColor(...COLOR_PRIMARY);
  doc.setLineWidth(0.6);
  doc.line(MARGIN, y, PAGE_WIDTH - MARGIN, y);
  y += 6;

  // ---------------- BILL TO block ----------------
  doc.setFontSize(8.5);
  const partyLines = doc.splitTextToSize([
    `M/s. ${bill.customer_name || '-'}`,
    [bill.address, bill.city, bill.state, bill.pincode].filter(Boolean).join(', '),
    [bill.mobile && `Contact: ${bill.mobile}`, bill.buyer_gstin && `GSTIN: ${bill.buyer_gstin}`, bill.buyer_pan && `PAN: ${bill.buyer_pan}`].filter(Boolean).join('   '),
  ].filter(Boolean).join('\n'), CONTENT_WIDTH - 6);
  const billToBoxHeight = 10 + partyLines.length * 4;
  ensureRoom(billToBoxHeight + 10);
  doc.setDrawColor(...COLOR_BORDER);
  doc.setLineWidth(0.2);
  doc.setFillColor(...COLOR_HEADER_BG);
  doc.rect(MARGIN, y, CONTENT_WIDTH, 6, 'F');
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(8);
  doc.setTextColor(...COLOR_PRIMARY);
  doc.text(bill.party_label || 'BILL TO', MARGIN + 3, y + 4.2);
  doc.rect(MARGIN, y, CONTENT_WIDTH, billToBoxHeight);
  doc.line(MARGIN, y + 6, PAGE_WIDTH - MARGIN, y + 6);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8.5);
  doc.setTextColor(...COLOR_MUTED);
  partyLines.forEach((line, index) => doc.text(line, MARGIN + 3, y + 11 + index * 4));

  y += billToBoxHeight + 6;
  const reference = bill.original_invoice_no || bill.original_bill_no || bill.reference;
  if (reference) writeLines(`Reference: ${reference}`);
  if (bill.return_reason) writeLines(`Return reason: ${bill.return_reason}`);
  if (bill.due_date) writeLines(`Due date: ${formatDate(bill.due_date)}`);
  if (bill.show_shipping_address_on_bill) {
    writeLines(['Ship to:', bill.ship_to, bill.ship_to_address, bill.shipping_state].filter(Boolean).join(' '));
  }
  y += 3;

  // ---------------- ITEMS TABLE ----------------
  const columns = [
    { key: 'sn', label: 'S.N.', x: MARGIN, width: 10, align: 'left' },
    { key: 'name', label: 'DESCRIPTION', x: MARGIN + 10, width: 43, align: 'left' },
    { key: 'hsn', label: 'HSN/SAC', x: MARGIN + 53, width: 19, align: 'center' },
    { key: 'qty', label: 'QTY', x: MARGIN + 72, width: 12, align: 'right' },
    { key: 'unit', label: 'UNIT', x: MARGIN + 84, width: 14, align: 'center' },
    { key: 'rate', label: 'RATE', x: MARGIN + 98, width: 23, align: 'right' },
    { key: 'discount', label: 'DISCOUNT', x: MARGIN + 121, width: 21, align: 'right' },
    { key: 'gst', label: 'GST %', x: MARGIN + 142, width: 14, align: 'right' },
    { key: 'amount', label: 'AMOUNT', x: MARGIN + 156, width: 30, align: 'right' },
  ];

  const rowHeight = 7;
  const headerHeight = 8;

  function drawTableHeader(yPos) {
    doc.setFillColor(...COLOR_HEADER_BG);
    doc.rect(MARGIN, yPos, CONTENT_WIDTH, headerHeight, 'F');
    doc.setDrawColor(...COLOR_BORDER);
    doc.rect(MARGIN, yPos, CONTENT_WIDTH, headerHeight);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(7.5);
    doc.setTextColor(...COLOR_PRIMARY);
    columns.forEach((col) => {
      const textX = col.align === 'right' ? col.x + col.width - 2 : col.align === 'center' ? col.x + col.width / 2 : col.x + 2;
      doc.text(col.label, textX, yPos + 5.3, { align: col.align === 'left' ? 'left' : col.align });
    });
    return yPos + headerHeight;
  }

  ensureRoom(headerHeight + rowHeight);
  y = drawTableHeader(y);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8.5);
  doc.setTextColor(...COLOR_TEXT);

  items.forEach((item, index) => {
    // New page if we run out of room (leaves space for totals section)
    const description = doc.splitTextToSize(item.item_name || '', 39);
    const itemHeight = Math.max(rowHeight, description.length * 4 + 3);
    if (y + itemHeight > PAGE_HEIGHT - MARGIN) {
      doc.addPage();
      y = MARGIN;
      y = drawTableHeader(y);
    }

    doc.setDrawColor(...COLOR_BORDER);
    doc.rect(MARGIN, y, CONTENT_WIDTH, itemHeight);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(7.5);
    doc.setTextColor(...COLOR_TEXT);

    const cells = {
      sn: String(index + 1),
      name: item.item_name,
      hsn: item.hsn_code || '—',
      qty: String(item.quantity),
      unit: item.unit || '—',
      rate: formatINR(item.rate),
      discount: item.discount_display ?? formatINR(item.discount_amount),
      gst: `${item.gst_percent}%`,
      amount: formatINR(item.line_total),
    };

    columns.forEach((col) => {
      const textX = col.align === 'right' ? col.x + col.width - 2 : col.align === 'center' ? col.x + col.width / 2 : col.x + 2;
      let text = cells[col.key];
      if (col.key === 'name') text = description;
      doc.text(text, textX, y + 4.7, { align: col.align === 'left' ? 'left' : col.align });
    });

    y += itemHeight;
  });

  // Close the table with a bottom border
  doc.setDrawColor(...COLOR_BORDER);
  doc.line(MARGIN, y, PAGE_WIDTH - MARGIN, y);
  y += 8;

  // ---------------- TERMS (left) + TOTALS (right) ----------------
  const leftWidth = 100;
  const rightX = MARGIN + leftWidth + 6;
  const rightWidth = CONTENT_WIDTH - leftWidth - 6;
  ensureRoom(52);
  const sectionTop = y;
  const sectionPage = doc.getNumberOfPages();

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(8);
  doc.setTextColor(...COLOR_PRIMARY);
  doc.text('TERMS & CONDITIONS', MARGIN, y + 3);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(7.5);
  doc.setTextColor(...COLOR_MUTED);
  y += 4;
  (company.terms_and_conditions || []).forEach((line, i) => writeLines(`${i + 1}. ${line}`, leftWidth, MARGIN, 3.6));

  if (bill.remarks) {
    y += 3;
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(8);
    doc.setTextColor(...COLOR_TEXT);
    writeLines('Remarks:', leftWidth);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(7.5);
    doc.setTextColor(...COLOR_MUTED);
    writeLines(bill.remarks, leftWidth, MARGIN, 3.6);
  }
  const termsPage = doc.getNumberOfPages();
  const termsY = y;
  doc.setPage(sectionPage);

  // Totals box
  const totalsRows = isInterstate
    ? [['Taxable Amount', bill.taxable_amount], ['IGST', bill.igst_amount]]
    : [['Taxable Amount', bill.taxable_amount], ['CGST', bill.cgst_amount], ['SGST', bill.sgst_amount]];
  totalsRows.push(['Round Off', bill.round_off]);

  const totalsBoxHeight = (totalsRows.length + 1) * 6.5 + 6;
  doc.setDrawColor(...COLOR_BORDER);
  doc.rect(rightX, sectionTop, rightWidth, totalsBoxHeight);

  let totalsY = sectionTop + 6;
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8.5);
  totalsRows.forEach(([label, value]) => {
    doc.setTextColor(...COLOR_MUTED);
    doc.text(label, rightX + 3, totalsY);
    doc.setTextColor(...COLOR_TEXT);
    doc.text(formatINR(value), rightX + rightWidth - 3, totalsY, { align: 'right' });
    totalsY += 6.5;
  });

  doc.setDrawColor(...COLOR_PRIMARY);
  doc.setLineWidth(0.4);
  doc.line(rightX + 2, totalsY - 3.5, rightX + rightWidth - 2, totalsY - 3.5);

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(10.5);
  doc.setTextColor(...COLOR_PRIMARY);
  doc.text('NET AMOUNT', rightX + 3, totalsY + 2.5);
  doc.text(formatINR(bill.grand_total), rightX + rightWidth - 3, totalsY + 2.5, { align: 'right' });

  doc.setPage(termsPage);
  y = (termsPage === sectionPage ? Math.max(termsY, sectionTop + totalsBoxHeight) : termsY) + 6;

  // Amount in words (already computed server-side by bill_service.py)
  doc.setFont('helvetica', 'italic');
  doc.setFontSize(8.5);
  doc.setTextColor(...COLOR_TEXT);
  if (bill.amount_in_words) writeLines(`Amount in Words: ${bill.amount_in_words}`);
  y += 10;

  // ---------------- SELLER / BUYER / SIGNATURE ----------------
  ensureRoom(40);
  doc.setDrawColor(...COLOR_BORDER);
  doc.line(MARGIN, y, PAGE_WIDTH - MARGIN, y);
  y += 6;

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(8);
  doc.setTextColor(...COLOR_PRIMARY);
  doc.text(bill.document_title ? 'COMPANY DETAILS' : "SELLER'S DETAILS", MARGIN, y);
  doc.text(bill.party_label ? `${bill.party_label} DETAILS` : "BUYER'S DETAILS", MARGIN + 70, y);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(7.5);
  doc.setTextColor(...COLOR_MUTED);
  let sellerY = y + 5;
  if (company.gstin) { doc.text(`GSTIN: ${company.gstin}`, MARGIN, sellerY); sellerY += 4.5; }
  if (company.pan_card) { doc.text(`PAN: ${company.pan_card}`, MARGIN, sellerY); sellerY += 4.5; }

  let buyerY = y + 5;
  if (bill.buyer_gstin) { doc.text(`GSTIN: ${bill.buyer_gstin}`, MARGIN + 70, buyerY); buyerY += 4.5; }
  if (bill.buyer_pan) { doc.text(`PAN: ${bill.buyer_pan}`, MARGIN + 70, buyerY); buyerY += 4.5; }

  // Signature block (right side)
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8.5);
  doc.setTextColor(...COLOR_TEXT);
  doc.text(doc.splitTextToSize(`For, ${company.company_name || ''}`, 65), PAGE_WIDTH - MARGIN, y + 3, { align: 'right' });
  doc.setDrawColor(...COLOR_MUTED);
  doc.line(PAGE_WIDTH - MARGIN - 40, y + 20, PAGE_WIDTH - MARGIN, y + 20);
  doc.setFontSize(7.5);
  doc.setTextColor(...COLOR_MUTED);
  doc.text('Owner Signature', PAGE_WIDTH - MARGIN, y + 24, { align: 'right' });

  y += Math.max(sellerY - y, buyerY - y, 24) + 4;

  // For short invoices (few items), anchor the footer near the bottom of
  // the page rather than leaving a large empty gap right after the
  // signature block — keeps the printed page looking balanced regardless
  // of item count.
  doc.setFontSize(7.5);
  const bankLines = doc.splitTextToSize(
    `A/C Name: ${company.bank_account_name || '-'}   A/C No.: ${company.bank_account_no || '-'}   IFSC: ${company.bank_ifsc || '-'}   Bank: ${company.bank_name || '-'}`, CONTENT_WIDTH);
  const jurisdictionLines = doc.splitTextToSize(company.jurisdiction_note || '', CONTENT_WIDTH - 6);
  const footerHeight = 13 + bankLines.length * 4 + Math.max(7, jurisdictionLines.length * 4 + 3);
  ensureRoom(footerHeight);
  const bankAnchorY = PAGE_HEIGHT - MARGIN - footerHeight;
  if (y < bankAnchorY) y = bankAnchorY;

  // Bank details
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(7.5);
  doc.setTextColor(...COLOR_TEXT);
  doc.text("Company's Bank Details:", MARGIN, y);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(...COLOR_MUTED);
  bankLines.forEach((line, index) => doc.text(line, MARGIN, y + 4 + index * 4));
  y += 8 + bankLines.length * 4;

  // ---------------- JURISDICTION FOOTER ----------------
  doc.setDrawColor(...COLOR_BORDER);
  doc.setFillColor(...COLOR_HEADER_BG);
  const jurisdictionHeight = Math.max(7, jurisdictionLines.length * 4 + 3);
  doc.rect(MARGIN, y, CONTENT_WIDTH, jurisdictionHeight, 'F');
  doc.rect(MARGIN, y, CONTENT_WIDTH, jurisdictionHeight);
  doc.setFont('helvetica', 'italic');
  doc.setFontSize(7.5);
  doc.setTextColor(...COLOR_MUTED);
  jurisdictionLines.forEach((line, index) => doc.text(line, PAGE_WIDTH / 2, y + 4.7 + index * 4, { align: 'center' }));

  return doc;
}

export function downloadInvoicePDF(billDetail, company = {}, options = {}) {
  return downloadDocumentPDF('sale', billDetail, company, options);
}

export function downloadDocumentPDF(type, data, company, options = {}) {
  const detail = documentPdfData(type, data);
  const doc = generateInvoicePDF(detail, company, options);
  const suffix = options.includeLetterhead === false ? 'without-letterhead' : 'with-letterhead';
  doc.save(`${type}_${String(detail.bill.invoice_no).replace(/[^a-zA-Z0-9_-]/g, '-')}-${suffix}.pdf`);
}
