import { useEffect, useReducer, useState } from 'react';
import { useToast } from '../context/ToastContext';
import { extractErrorMessage } from '../services/api';
import { historyPosition } from '../utils/pagination';

// All history requests share reset, stale-response protection and page recovery.
export default function useHistoryPage(fetchPage, filters) {
  const toast = useToast();
  const filterKey = JSON.stringify(filters);
  const [position, dispatch] = useReducer(historyPosition, { filterKey, page: 1, pageSize: 20 });
  const [result, setResult] = useState({ items: [], total: 0, total_pages: 0 });
  const [revision, setRevision] = useState(0);

  // Adjust before effects run so new filters never request the previous page.
  if (position.filterKey !== filterKey) {
    dispatch({ type: 'filters', value: filterKey });
  }
  const { page, pageSize } = position;
  const requestKey = JSON.stringify([filterKey, page, pageSize, revision]);
  const loading = result.requestKey !== requestKey;

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const data = await fetchPage({ ...JSON.parse(filterKey), page, pageSize });
        if (cancelled) return;
        const lastPage = Math.max(1, data.total_pages);
        if (page > lastPage) {
          dispatch({ type: 'recover', value: lastPage });
          return;
        }
        setResult({ ...data, requestKey });
      } catch (error) {
        if (!cancelled) {
          setResult({ items: [], total: 0, total_pages: 0, requestKey });
          toast.error(extractErrorMessage(error));
        }
      }
    }, 350);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [fetchPage, filterKey, page, pageSize, requestKey, toast]);

  return {
    items: result.items,
    loading,
    reload: () => setRevision((value) => value + 1),
    pagination: {
      page, pageSize, total: result.total, totalPages: result.total_pages, loading,
      onPageChange: (next) => dispatch({ type: 'page', value: next }),
      onPageSizeChange: (size) => dispatch({ type: 'size', value: size }),
    },
  };
}
