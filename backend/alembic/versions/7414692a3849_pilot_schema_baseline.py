"""Complete pilot schema baseline.

Revision ID: 7414692a3849
Revises: None

Replaces the incomplete, unreleased three-revision history. The audited developer
DB is already at this revision and requires no stamp or replay. This is a frozen
schema snapshot: future model changes require new migrations.
"""
from alembic import op
import sqlalchemy as sa

revision = "7414692a3849"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE party_code_seq START WITH 1")
    op.execute("CREATE SEQUENCE customer_code_seq START WITH 1")
    # Frozen model snapshot, parents before children.
    op.create_table('banks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_banks_id'), 'banks', ['id'], unique=False)
    op.create_index(op.f('ix_banks_name'), 'banks', ['name'], unique=False)
    op.create_table('company_profile',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('company_name', sa.String(length=255), nullable=False),
    sa.Column('address_line1', sa.String(length=255), nullable=True),
    sa.Column('address_line2', sa.String(length=255), nullable=True),
    sa.Column('mobile', sa.String(length=30), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('gstin', sa.String(length=15), nullable=True),
    sa.Column('pan_card', sa.String(length=10), nullable=True),
    sa.Column('udyam_no', sa.String(length=100), nullable=True),
    sa.Column('bank_account_name', sa.String(length=255), nullable=True),
    sa.Column('bank_account_no', sa.String(length=100), nullable=True),
    sa.Column('bank_ifsc', sa.String(length=50), nullable=True),
    sa.Column('bank_name', sa.String(length=255), nullable=True),
    sa.Column('terms_and_conditions', sa.JSON(), nullable=False),
    sa.Column('jurisdiction_note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_company_profile_id'), 'company_profile', ['id'], unique=False)
    op.create_table('customers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('customer_name', sa.String(), nullable=False),
    sa.Column('customer_code', sa.String(length=30), nullable=True),
    sa.Column('mobile', sa.String(length=10), nullable=False),
    sa.Column('email', sa.String(), nullable=True),
    sa.Column('address', sa.String(), nullable=False),
    sa.Column('city', sa.String(), nullable=False),
    sa.Column('state', sa.String(), nullable=False),
    sa.Column('pincode', sa.String(), nullable=True),
    sa.Column('gstin', sa.String(length=15), nullable=True),
    sa.Column('pan_card', sa.String(length=10), nullable=True),
    sa.Column('state_code', sa.String(length=2), nullable=True),
    sa.Column('remarks', sa.String(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('gstin'),
    sa.UniqueConstraint('pan_card')
    )
    op.create_index(op.f('ix_customers_customer_code'), 'customers', ['customer_code'], unique=True)
    op.create_index(op.f('ix_customers_customer_name'), 'customers', ['customer_name'], unique=False)
    op.create_index(op.f('ix_customers_id'), 'customers', ['id'], unique=False)
    op.create_table('doneby',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_doneby_id'), 'doneby', ['id'], unique=False)
    op.create_index(op.f('ix_doneby_name'), 'doneby', ['name'], unique=False)
    op.create_table('item_master',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('code', sa.String(), nullable=True),
    sa.Column('hsn_code', sa.String(), nullable=False),
    sa.Column('unit', sa.String(), nullable=False),
    sa.Column('current_stock', sa.Float(), nullable=True),
    sa.Column('purchase_price', sa.Float(), nullable=True),
    sa.Column('sale_price', sa.Float(), nullable=True),
    sa.Column('mrp', sa.Float(), nullable=True),
    sa.Column('cgst', sa.Float(), nullable=True),
    sa.Column('sgst', sa.Float(), nullable=True),
    sa.Column('category', sa.String(), nullable=True),
    sa.Column('brand', sa.String(), nullable=True),
    sa.Column('description', sa.String(), nullable=True),
    sa.Column('last_purchase_date', sa.Date(), nullable=True),
    sa.Column('last_sale_date', sa.Date(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_index(op.f('ix_item_master_id'), 'item_master', ['id'], unique=False)
    op.create_index(op.f('ix_item_master_name'), 'item_master', ['name'], unique=True)
    op.create_table('parties',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('party_code', sa.String(length=30), nullable=True),
    sa.Column('party_type', sa.String(), nullable=True),
    sa.Column('country_code', sa.String(length=10), nullable=True),
    sa.Column('mobile', sa.String(length=20), nullable=True),
    sa.Column('address', sa.String(), nullable=True),
    sa.Column('city', sa.String(), nullable=True),
    sa.Column('state', sa.String(), nullable=True),
    sa.Column('gstin', sa.String(length=15), nullable=True),
    sa.Column('pan_card', sa.String(length=10), nullable=True),
    sa.Column('opening_balance', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('balance_type', sa.String(length=10), nullable=False),
    sa.Column('opening_remark', sa.Text(), nullable=True),
    sa.Column('current_balance', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('current_balance_type', sa.String(length=10), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_parties_gstin'), 'parties', ['gstin'], unique=True)
    op.create_index(op.f('ix_parties_id'), 'parties', ['id'], unique=False)
    op.create_index(op.f('ix_parties_name'), 'parties', ['name'], unique=False)
    op.create_index(op.f('ix_parties_pan_card'), 'parties', ['pan_card'], unique=False)
    op.create_index(op.f('ix_parties_party_code'), 'parties', ['party_code'], unique=True)
    op.create_table('bill',
    sa.Column('bill_id', sa.Integer(), nullable=False),
    sa.Column('invoice_no', sa.String(length=30), nullable=False),
    sa.Column('customer_id', sa.Integer(), nullable=False),
    sa.Column('bill_date', sa.Date(), nullable=False),
    sa.Column('due_term', sa.Integer(), nullable=True),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('is_interstate', sa.Boolean(), nullable=False),
    sa.Column('customer_name', sa.String(length=100), nullable=False),
    sa.Column('mobile', sa.String(length=15), nullable=False),
    sa.Column('email', sa.String(length=100), nullable=True),
    sa.Column('address', sa.String(length=255), nullable=False),
    sa.Column('city', sa.String(length=100), nullable=False),
    sa.Column('state', sa.String(length=100), nullable=False),
    sa.Column('pincode', sa.String(length=10), nullable=True),
    sa.Column('buyer_gstin', sa.String(length=15), nullable=True),
    sa.Column('buyer_pan', sa.String(length=10), nullable=True),
    sa.Column('buyer_state_code', sa.String(length=2), nullable=True),
    sa.Column('done_by', sa.String(length=100), nullable=True),
    sa.Column('brokerage', sa.Float(), nullable=False),
    sa.Column('broker_remarks', sa.String(length=500), nullable=True),
    sa.Column('total_boxes', sa.Integer(), nullable=False),
    sa.Column('subtotal', sa.Float(), nullable=False),
    sa.Column('discount_amount', sa.Float(), nullable=False),
    sa.Column('taxable_amount', sa.Float(), nullable=False),
    sa.Column('cgst_amount', sa.Float(), nullable=False),
    sa.Column('sgst_amount', sa.Float(), nullable=False),
    sa.Column('igst_amount', sa.Float(), nullable=False),
    sa.Column('grand_total', sa.Float(), nullable=False),
    sa.Column('amount_in_words', sa.String(length=300), nullable=False),
    sa.Column('delivery_date', sa.Date(), nullable=True),
    sa.Column('ship_to', sa.String(length=200), nullable=True),
    sa.Column('ship_to_address', sa.String(length=500), nullable=True),
    sa.Column('shipping_state', sa.String(length=100), nullable=True),
    sa.Column('transport', sa.String(length=200), nullable=True),
    sa.Column('reference', sa.String(length=200), nullable=True),
    sa.Column('remarks', sa.String(length=500), nullable=True),
    sa.Column('show_shipping_address_on_bill', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
    sa.PrimaryKeyConstraint('bill_id')
    )
    op.create_index(op.f('ix_bill_bill_id'), 'bill', ['bill_id'], unique=False)
    op.create_index(op.f('ix_bill_invoice_no'), 'bill', ['invoice_no'], unique=True)
    op.create_table('purchase_returns',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('return_no', sa.String(length=100), nullable=False),
    sa.Column('order_no', sa.String(length=100), nullable=True),
    sa.Column('original_bill_no', sa.String(length=100), nullable=True),
    sa.Column('return_date', sa.Date(), nullable=False),
    sa.Column('due_term', sa.Integer(), nullable=True),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('party_id', sa.Integer(), nullable=False),
    sa.Column('is_gst', sa.Boolean(), nullable=False),
    sa.Column('address', sa.Text(), nullable=True),
    sa.Column('city', sa.String(length=150), nullable=True),
    sa.Column('party_state', sa.String(length=100), nullable=True),
    sa.Column('contact_no', sa.String(length=30), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('done_by', sa.String(length=100), nullable=True),
    sa.Column('brokerage', sa.Float(), nullable=False),
    sa.Column('broker_remarks', sa.String(length=500), nullable=True),
    sa.Column('return_reason', sa.String(length=500), nullable=False),
    sa.Column('taxable_amount', sa.Float(), nullable=False),
    sa.Column('sgst_total', sa.Float(), nullable=False),
    sa.Column('cgst_total', sa.Float(), nullable=False),
    sa.Column('igst_total', sa.Float(), nullable=False),
    sa.Column('round_off', sa.Float(), nullable=False),
    sa.Column('grand_total', sa.Float(), nullable=False),
    sa.Column('delivery_date', sa.Date(), nullable=True),
    sa.Column('transport', sa.String(length=200), nullable=True),
    sa.Column('ship_to', sa.String(length=200), nullable=True),
    sa.Column('ship_to_address', sa.Text(), nullable=True),
    sa.Column('state', sa.String(length=100), nullable=True),
    sa.Column('reference', sa.String(length=200), nullable=True),
    sa.Column('remarks', sa.Text(), nullable=True),
    sa.Column('show_shipping_address_on_bill', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['party_id'], ['parties.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_purchase_returns_id'), 'purchase_returns', ['id'], unique=False)
    op.create_index(op.f('ix_purchase_returns_order_no'), 'purchase_returns', ['order_no'], unique=False)
    op.create_index(op.f('ix_purchase_returns_original_bill_no'), 'purchase_returns', ['original_bill_no'], unique=False)
    op.create_index(op.f('ix_purchase_returns_party_id'), 'purchase_returns', ['party_id'], unique=False)
    op.create_index(op.f('ix_purchase_returns_return_no'), 'purchase_returns', ['return_no'], unique=True)
    op.create_table('purchases',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('bill_no', sa.String(length=100), nullable=False),
    sa.Column('order_no', sa.String(length=100), nullable=True),
    sa.Column('bill_date', sa.Date(), nullable=False),
    sa.Column('due_term', sa.Integer(), nullable=True),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('party_id', sa.Integer(), nullable=False),
    sa.Column('is_gst', sa.Boolean(), nullable=False),
    sa.Column('contact_person', sa.String(length=150), nullable=True),
    sa.Column('contact_no', sa.String(length=30), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('done_by', sa.String(length=100), nullable=True),
    sa.Column('brokerage', sa.Float(), nullable=False),
    sa.Column('broker_remarks', sa.String(length=500), nullable=True),
    sa.Column('taxable_amount', sa.Float(), nullable=False),
    sa.Column('sgst_total', sa.Float(), nullable=False),
    sa.Column('cgst_total', sa.Float(), nullable=False),
    sa.Column('igst_total', sa.Float(), nullable=False),
    sa.Column('round_off', sa.Float(), nullable=False),
    sa.Column('grand_total', sa.Float(), nullable=False),
    sa.Column('delivery_date', sa.Date(), nullable=True),
    sa.Column('transport', sa.String(length=200), nullable=True),
    sa.Column('ship_to', sa.String(length=200), nullable=True),
    sa.Column('ship_to_address', sa.String(length=1000), nullable=True),
    sa.Column('state', sa.String(length=100), nullable=True),
    sa.Column('reference', sa.String(length=200), nullable=True),
    sa.Column('remarks', sa.String(length=1000), nullable=True),
    sa.Column('show_shipping_address_on_bill', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['party_id'], ['parties.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_purchases_bill_no'), 'purchases', ['bill_no'], unique=True)
    op.create_index(op.f('ix_purchases_id'), 'purchases', ['id'], unique=False)
    op.create_index(op.f('ix_purchases_order_no'), 'purchases', ['order_no'], unique=False)
    op.create_index(op.f('ix_purchases_party_id'), 'purchases', ['party_id'], unique=False)
    op.create_table('quotations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('quotation_no', sa.String(length=100), nullable=False),
    sa.Column('order_no', sa.String(length=100), nullable=True),
    sa.Column('quotation_date', sa.Date(), nullable=False),
    sa.Column('due_term', sa.Integer(), nullable=True),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('customer_id', sa.Integer(), nullable=False),
    sa.Column('is_gst', sa.Boolean(), nullable=False),
    sa.Column('address', sa.Text(), nullable=True),
    sa.Column('city', sa.String(length=150), nullable=True),
    sa.Column('state', sa.String(length=100), nullable=True),
    sa.Column('contact_no', sa.String(length=30), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('done_by', sa.String(length=100), nullable=True),
    sa.Column('brokerage', sa.Float(), nullable=False),
    sa.Column('broker_remarks', sa.String(length=500), nullable=True),
    sa.Column('taxable_amount', sa.Float(), nullable=False),
    sa.Column('sgst_total', sa.Float(), nullable=False),
    sa.Column('cgst_total', sa.Float(), nullable=False),
    sa.Column('igst_total', sa.Float(), nullable=False),
    sa.Column('round_off', sa.Float(), nullable=False),
    sa.Column('grand_total', sa.Float(), nullable=False),
    sa.Column('delivery_date', sa.Date(), nullable=True),
    sa.Column('ship_to', sa.String(length=200), nullable=True),
    sa.Column('ship_to_address', sa.Text(), nullable=True),
    sa.Column('shipping_state', sa.String(length=100), nullable=True),
    sa.Column('transport', sa.String(length=200), nullable=True),
    sa.Column('reference', sa.String(length=200), nullable=True),
    sa.Column('remarks', sa.Text(), nullable=True),
    sa.Column('show_shipping_address_on_bill', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quotations_customer_id'), 'quotations', ['customer_id'], unique=False)
    op.create_index(op.f('ix_quotations_id'), 'quotations', ['id'], unique=False)
    op.create_index(op.f('ix_quotations_order_no'), 'quotations', ['order_no'], unique=False)
    op.create_index(op.f('ix_quotations_quotation_no'), 'quotations', ['quotation_no'], unique=True)
    op.create_table('rojmel',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('transaction_type', sa.Enum('CR_PAY', 'DR_PAY', 'CASH_BANK', 'JV', name='transactiontype'), nullable=False),
    sa.Column('receipt_no', sa.String(length=50), nullable=False),
    sa.Column('given_taken_date', sa.Date(), nullable=False),
    sa.Column('effective_date', sa.Date(), nullable=False),
    sa.Column('party_id', sa.Integer(), nullable=True),
    sa.Column('cash_bank_id', sa.Integer(), nullable=False),
    sa.Column('done_by_id', sa.Integer(), nullable=False),
    sa.Column('pay_mode', sa.String(length=20), nullable=False),
    sa.Column('cheque_txn_no', sa.String(length=100), nullable=True),
    sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('sgst_percent', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('cgst_percent', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('igst_percent', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('net_amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('payment_for', sa.String(length=255), nullable=True),
    sa.Column('remarks', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['cash_bank_id'], ['banks.id'], ),
    sa.ForeignKeyConstraint(['done_by_id'], ['doneby.id'], ),
    sa.ForeignKeyConstraint(['party_id'], ['parties.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rojmel_id'), 'rojmel', ['id'], unique=False)
    op.create_index(op.f('ix_rojmel_receipt_no'), 'rojmel', ['receipt_no'], unique=True)
    op.create_table('sales_returns',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('return_no', sa.String(length=100), nullable=False),
    sa.Column('order_no', sa.String(length=100), nullable=True),
    sa.Column('original_invoice_no', sa.String(length=100), nullable=True),
    sa.Column('return_date', sa.Date(), nullable=False),
    sa.Column('due_term', sa.Integer(), nullable=True),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('customer_id', sa.Integer(), nullable=False),
    sa.Column('is_gst', sa.Boolean(), nullable=False),
    sa.Column('address', sa.Text(), nullable=True),
    sa.Column('city', sa.String(length=150), nullable=True),
    sa.Column('state', sa.String(length=100), nullable=True),
    sa.Column('contact_no', sa.String(length=30), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('done_by', sa.String(length=100), nullable=True),
    sa.Column('brokerage', sa.Float(), nullable=False),
    sa.Column('broker_remarks', sa.String(length=500), nullable=True),
    sa.Column('return_reason', sa.String(length=500), nullable=False),
    sa.Column('taxable_amount', sa.Float(), nullable=False),
    sa.Column('sgst_total', sa.Float(), nullable=False),
    sa.Column('cgst_total', sa.Float(), nullable=False),
    sa.Column('igst_total', sa.Float(), nullable=False),
    sa.Column('round_off', sa.Float(), nullable=False),
    sa.Column('grand_total', sa.Float(), nullable=False),
    sa.Column('delivery_date', sa.Date(), nullable=True),
    sa.Column('ship_to', sa.String(length=200), nullable=True),
    sa.Column('ship_to_address', sa.Text(), nullable=True),
    sa.Column('shipping_state', sa.String(length=100), nullable=True),
    sa.Column('transport', sa.String(length=200), nullable=True),
    sa.Column('reference', sa.String(length=200), nullable=True),
    sa.Column('remarks', sa.Text(), nullable=True),
    sa.Column('show_shipping_address_on_bill', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sales_returns_customer_id'), 'sales_returns', ['customer_id'], unique=False)
    op.create_index(op.f('ix_sales_returns_id'), 'sales_returns', ['id'], unique=False)
    op.create_index(op.f('ix_sales_returns_order_no'), 'sales_returns', ['order_no'], unique=False)
    op.create_index(op.f('ix_sales_returns_original_invoice_no'), 'sales_returns', ['original_invoice_no'], unique=False)
    op.create_index(op.f('ix_sales_returns_return_no'), 'sales_returns', ['return_no'], unique=True)
    op.create_table('bill_item',
    sa.Column('bill_item_id', sa.Integer(), nullable=False),
    sa.Column('bill_id', sa.Integer(), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('item_name', sa.String(length=150), nullable=False),
    sa.Column('brand_name', sa.String(length=100), nullable=True),
    sa.Column('hsn_code', sa.String(length=20), nullable=False),
    sa.Column('unit', sa.String(length=20), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('rate', sa.Float(), nullable=False),
    sa.Column('discount_amount', sa.Float(), nullable=True),
    sa.Column('taxable_amount', sa.Float(), nullable=False),
    sa.Column('gst_percent', sa.Float(), nullable=False),
    sa.Column('cgst_percent', sa.Float(), nullable=True),
    sa.Column('sgst_percent', sa.Float(), nullable=True),
    sa.Column('igst_percent', sa.Float(), nullable=True),
    sa.Column('cgst_amount', sa.Float(), nullable=True),
    sa.Column('sgst_amount', sa.Float(), nullable=True),
    sa.Column('igst_amount', sa.Float(), nullable=True),
    sa.Column('line_total', sa.Float(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['bill_id'], ['bill.bill_id'], ),
    sa.ForeignKeyConstraint(['item_id'], ['item_master.id'], ),
    sa.PrimaryKeyConstraint('bill_item_id')
    )
    op.create_index(op.f('ix_bill_item_bill_item_id'), 'bill_item', ['bill_item_id'], unique=False)
    op.create_table('purchase_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('purchase_id', sa.Integer(), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('item_name', sa.String(length=255), nullable=False),
    sa.Column('hsn_code', sa.String(length=50), nullable=False),
    sa.Column('quantity', sa.Float(), nullable=False),
    sa.Column('unit', sa.String(length=50), nullable=False),
    sa.Column('price', sa.Float(), nullable=False),
    sa.Column('disc_percent', sa.Float(), nullable=False),
    sa.Column('sgst', sa.Float(), nullable=False),
    sa.Column('cgst', sa.Float(), nullable=False),
    sa.Column('igst', sa.Float(), nullable=False),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['item_id'], ['item_master.id'], ),
    sa.ForeignKeyConstraint(['purchase_id'], ['purchases.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_purchase_items_id'), 'purchase_items', ['id'], unique=False)
    op.create_index(op.f('ix_purchase_items_item_id'), 'purchase_items', ['item_id'], unique=False)
    op.create_index(op.f('ix_purchase_items_purchase_id'), 'purchase_items', ['purchase_id'], unique=False)
    op.create_table('purchase_return_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('purchase_return_id', sa.Integer(), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=True),
    sa.Column('item_name', sa.String(length=255), nullable=False),
    sa.Column('hsn_code', sa.String(length=50), nullable=False),
    sa.Column('quantity', sa.Float(), nullable=False),
    sa.Column('unit', sa.String(length=50), nullable=False),
    sa.Column('price', sa.Float(), nullable=False),
    sa.Column('disc_percent', sa.Float(), nullable=False),
    sa.Column('sgst', sa.Float(), nullable=False),
    sa.Column('cgst', sa.Float(), nullable=False),
    sa.Column('igst', sa.Float(), nullable=False),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['item_id'], ['item_master.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['purchase_return_id'], ['purchase_returns.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_purchase_return_items_id'), 'purchase_return_items', ['id'], unique=False)
    op.create_index(op.f('ix_purchase_return_items_item_id'), 'purchase_return_items', ['item_id'], unique=False)
    op.create_index(op.f('ix_purchase_return_items_purchase_return_id'), 'purchase_return_items', ['purchase_return_id'], unique=False)
    op.create_table('quotation_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('quotation_id', sa.Integer(), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=True),
    sa.Column('item_name', sa.String(length=255), nullable=False),
    sa.Column('hsn_code', sa.String(length=50), nullable=False),
    sa.Column('quantity', sa.Float(), nullable=False),
    sa.Column('unit', sa.String(length=50), nullable=False),
    sa.Column('price', sa.Float(), nullable=False),
    sa.Column('disc_percent', sa.Float(), nullable=False),
    sa.Column('sgst', sa.Float(), nullable=False),
    sa.Column('cgst', sa.Float(), nullable=False),
    sa.Column('igst', sa.Float(), nullable=False),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['item_id'], ['item_master.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['quotation_id'], ['quotations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quotation_items_id'), 'quotation_items', ['id'], unique=False)
    op.create_index(op.f('ix_quotation_items_item_id'), 'quotation_items', ['item_id'], unique=False)
    op.create_index(op.f('ix_quotation_items_quotation_id'), 'quotation_items', ['quotation_id'], unique=False)
    op.create_table('sales_return_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sales_return_id', sa.Integer(), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=True),
    sa.Column('item_name', sa.String(length=255), nullable=False),
    sa.Column('hsn_code', sa.String(length=50), nullable=False),
    sa.Column('quantity', sa.Float(), nullable=False),
    sa.Column('unit', sa.String(length=50), nullable=False),
    sa.Column('price', sa.Float(), nullable=False),
    sa.Column('disc_percent', sa.Float(), nullable=False),
    sa.Column('sgst', sa.Float(), nullable=False),
    sa.Column('cgst', sa.Float(), nullable=False),
    sa.Column('igst', sa.Float(), nullable=False),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['item_id'], ['item_master.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['sales_return_id'], ['sales_returns.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sales_return_items_id'), 'sales_return_items', ['id'], unique=False)
    op.create_index(op.f('ix_sales_return_items_item_id'), 'sales_return_items', ['item_id'], unique=False)
    op.create_index(op.f('ix_sales_return_items_sales_return_id'), 'sales_return_items', ['sales_return_id'], unique=False)


def downgrade() -> None:
    # Reverse dependency order; only objects owned by this baseline.
    op.drop_index(op.f('ix_sales_return_items_sales_return_id'), table_name='sales_return_items')
    op.drop_index(op.f('ix_sales_return_items_item_id'), table_name='sales_return_items')
    op.drop_index(op.f('ix_sales_return_items_id'), table_name='sales_return_items')
    op.drop_table('sales_return_items')
    op.drop_index(op.f('ix_quotation_items_quotation_id'), table_name='quotation_items')
    op.drop_index(op.f('ix_quotation_items_item_id'), table_name='quotation_items')
    op.drop_index(op.f('ix_quotation_items_id'), table_name='quotation_items')
    op.drop_table('quotation_items')
    op.drop_index(op.f('ix_purchase_return_items_purchase_return_id'), table_name='purchase_return_items')
    op.drop_index(op.f('ix_purchase_return_items_item_id'), table_name='purchase_return_items')
    op.drop_index(op.f('ix_purchase_return_items_id'), table_name='purchase_return_items')
    op.drop_table('purchase_return_items')
    op.drop_index(op.f('ix_purchase_items_purchase_id'), table_name='purchase_items')
    op.drop_index(op.f('ix_purchase_items_item_id'), table_name='purchase_items')
    op.drop_index(op.f('ix_purchase_items_id'), table_name='purchase_items')
    op.drop_table('purchase_items')
    op.drop_index(op.f('ix_bill_item_bill_item_id'), table_name='bill_item')
    op.drop_table('bill_item')
    op.drop_index(op.f('ix_sales_returns_return_no'), table_name='sales_returns')
    op.drop_index(op.f('ix_sales_returns_original_invoice_no'), table_name='sales_returns')
    op.drop_index(op.f('ix_sales_returns_order_no'), table_name='sales_returns')
    op.drop_index(op.f('ix_sales_returns_id'), table_name='sales_returns')
    op.drop_index(op.f('ix_sales_returns_customer_id'), table_name='sales_returns')
    op.drop_table('sales_returns')
    op.drop_index(op.f('ix_rojmel_receipt_no'), table_name='rojmel')
    op.drop_index(op.f('ix_rojmel_id'), table_name='rojmel')
    op.drop_table('rojmel')
    op.drop_index(op.f('ix_quotations_quotation_no'), table_name='quotations')
    op.drop_index(op.f('ix_quotations_order_no'), table_name='quotations')
    op.drop_index(op.f('ix_quotations_id'), table_name='quotations')
    op.drop_index(op.f('ix_quotations_customer_id'), table_name='quotations')
    op.drop_table('quotations')
    op.drop_index(op.f('ix_purchases_party_id'), table_name='purchases')
    op.drop_index(op.f('ix_purchases_order_no'), table_name='purchases')
    op.drop_index(op.f('ix_purchases_id'), table_name='purchases')
    op.drop_index(op.f('ix_purchases_bill_no'), table_name='purchases')
    op.drop_table('purchases')
    op.drop_index(op.f('ix_purchase_returns_return_no'), table_name='purchase_returns')
    op.drop_index(op.f('ix_purchase_returns_party_id'), table_name='purchase_returns')
    op.drop_index(op.f('ix_purchase_returns_original_bill_no'), table_name='purchase_returns')
    op.drop_index(op.f('ix_purchase_returns_order_no'), table_name='purchase_returns')
    op.drop_index(op.f('ix_purchase_returns_id'), table_name='purchase_returns')
    op.drop_table('purchase_returns')
    op.drop_index(op.f('ix_bill_invoice_no'), table_name='bill')
    op.drop_index(op.f('ix_bill_bill_id'), table_name='bill')
    op.drop_table('bill')
    op.drop_index(op.f('ix_parties_party_code'), table_name='parties')
    op.drop_index(op.f('ix_parties_pan_card'), table_name='parties')
    op.drop_index(op.f('ix_parties_name'), table_name='parties')
    op.drop_index(op.f('ix_parties_id'), table_name='parties')
    op.drop_index(op.f('ix_parties_gstin'), table_name='parties')
    op.drop_table('parties')
    op.drop_index(op.f('ix_item_master_name'), table_name='item_master')
    op.drop_index(op.f('ix_item_master_id'), table_name='item_master')
    op.drop_table('item_master')
    op.drop_index(op.f('ix_doneby_name'), table_name='doneby')
    op.drop_index(op.f('ix_doneby_id'), table_name='doneby')
    op.drop_table('doneby')
    op.drop_index(op.f('ix_customers_id'), table_name='customers')
    op.drop_index(op.f('ix_customers_customer_name'), table_name='customers')
    op.drop_index(op.f('ix_customers_customer_code'), table_name='customers')
    op.drop_table('customers')
    op.drop_index(op.f('ix_company_profile_id'), table_name='company_profile')
    op.drop_table('company_profile')
    op.drop_index(op.f('ix_banks_name'), table_name='banks')
    op.drop_index(op.f('ix_banks_id'), table_name='banks')
    op.drop_table('banks')
    sa.Enum(name="transactiontype").drop(op.get_bind(), checkfirst=False)
    op.execute("DROP SEQUENCE customer_code_seq")
    op.execute("DROP SEQUENCE party_code_seq")
