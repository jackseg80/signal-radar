import React, { createContext, useContext, useState } from 'react';
import AssetModal from '../components/ui/AssetModal';

const AssetContext = createContext(null);

export function AssetProvider({ children }) {
  const [selectedSymbol, setSelectedSymbol] = useState(null);

  const openAsset = (symbol) => setSelectedSymbol(symbol);
  const closeAsset = () => setSelectedSymbol(null);

  return (
    <AssetContext.Provider value={{ openAsset }}>
      {children}
      {selectedSymbol && (
        <AssetModal
          symbol={selectedSymbol}
          onClose={closeAsset}
        />
      )}
    </AssetContext.Provider>
  );
}

export const useAssetView = () => useContext(AssetContext);
