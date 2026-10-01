import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { fetchCompanyProfile, DEFAULT_COMPANY_PROFILE } from '../services/companyService';

const CompanyContext = createContext(null);

export function CompanyProvider({ children }) {
  const [company, setCompany] = useState(DEFAULT_COMPANY_PROFILE);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    setLoading(true);
    return fetchCompanyProfile()
      .then(setCompany)
      .catch(() => setCompany(DEFAULT_COMPANY_PROFILE))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <CompanyContext.Provider value={{ company, loading, refresh }}>
      {children}
    </CompanyContext.Provider>
  );
}

export function useCompany() {
  const ctx = useContext(CompanyContext);
  if (!ctx) {
    throw new Error('useCompany must be used within a CompanyProvider');
  }
  return ctx;
}
