import { createContext, useContext, useState, useCallback, useEffect } from 'react';

const RefreshContext = createContext();

const POLL_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

export function RefreshProvider({ children }) {
  const [refreshKey, setRefreshKey] = useState(0);
  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  useEffect(() => {
    const id = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <RefreshContext.Provider value={{ refreshKey, refresh }}>
      {children}
    </RefreshContext.Provider>
  );
}

export function useRefresh() {
  return useContext(RefreshContext);
}
