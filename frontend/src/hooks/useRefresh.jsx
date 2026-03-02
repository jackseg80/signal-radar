import { createContext, useContext, useState, useCallback } from 'react';

const RefreshContext = createContext();

export function RefreshProvider({ children }) {
  const [refreshKey, setRefreshKey] = useState(0);
  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);
  return (
    <RefreshContext.Provider value={{ refreshKey, refresh }}>
      {children}
    </RefreshContext.Provider>
  );
}

export function useRefresh() {
  return useContext(RefreshContext);
}
