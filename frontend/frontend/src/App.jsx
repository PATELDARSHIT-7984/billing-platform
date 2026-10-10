import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ToastProvider } from './context/ToastContext';
import { CompanyProvider } from './context/CompanyContext';
import MainLayout from './components/layout/MainLayout';

import Dashboard from './pages/Dashboard';
import PartyManagement from './pages/PartyManagement';
import ItemMaster from './pages/ItemMaster';
import PurchaseEntry from './pages/Purchase/PurchaseEntry';
import PurchaseHistory from './pages/PurchaseHistory';
import PurchaseReturnEntry from './pages/PurchaseReturn/PurchaseReturnEntry';
import PurchaseReturnHistory from './pages/PurchaseReturnHistory';
import SalesEntry from './pages/SalesEntry';
import SalesHistory from './pages/SalesHistory';
import SalesReturnEntry from './pages/SalesReturnEntry';
import SalesReturnHistory from './pages/SalesReturnHistory';
import QuotationEntry from './pages/QuotationEntry';
import QuotationHistory from './pages/QuotationHistory';
import Reports from './pages/Reports';
import CompanySettings from './pages/CompanySettings';
import RojmelManagement from './pages/RojmelManagement';
import BankManagement from './pages/BankManagement';
import DoneByManagement from './pages/DoneByManagement';

export default function App() {
  return (
    <ToastProvider>
      <CompanyProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<MainLayout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/parties" element={<PartyManagement />} />
              <Route path="/customers" element={<PartyManagement legacyCustomer />} />
              <Route path="/items" element={<ItemMaster />} />
              <Route path="/purchase-entry" element={<PurchaseEntry />} />
              <Route path="/purchase-history" element={<PurchaseHistory />} />
              <Route path="/purchase-return-entry" element={<PurchaseReturnEntry />} />
              <Route path="/purchase-return-history" element={<PurchaseReturnHistory />} />
              <Route path="/sales-entry" element={<SalesEntry />} />
              <Route path="/sales-history" element={<SalesHistory />} />
              <Route path="/sales-return-entry" element={<SalesReturnEntry />} />
              <Route path="/sales-return-history" element={<SalesReturnHistory />} />
              <Route path="/quotation-entry" element={<QuotationEntry />} />
              <Route path="/quotation-history" element={<QuotationHistory />} />
              <Route path="/bill-history" element={<SalesHistory />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/company-settings" element={<CompanySettings />} />
              <Route path="/rojmel" element={<RojmelManagement />} />
              {/* Not in the sidebar -- reached only via the "+" button next to Bank/Done By dropdowns. */}
              <Route path="/banks" element={<BankManagement />} />
              <Route path="/done-by" element={<DoneByManagement />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </CompanyProvider>
    </ToastProvider>
  );
}
