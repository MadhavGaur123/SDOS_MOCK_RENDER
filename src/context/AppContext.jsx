import React, { createContext, useCallback, useContext, useState } from "react";

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [compareCart, setCompareCart] = useState([]);
  const [myDocuments, setMyDocuments] = useState([]);
  const [chatContext, setChatContext] = useState(null);

  const addToCompare = useCallback((variant) => {
    setCompareCart((prev) => {
      if (prev.some((item) => item.variant_id === variant.variant_id)) {
        return prev;
      }

      if (prev.length >= 2) {
        return [prev[1], variant];
      }

      return [...prev, variant];
    });
  }, []);

  const removeFromCompare = useCallback((variantId) => {
    setCompareCart((prev) => prev.filter((item) => item.variant_id !== variantId));
  }, []);

  const clearCompare = useCallback(() => {
    setCompareCart([]);
  }, []);

  const isInCompare = useCallback(
    (variantId) => compareCart.some((item) => item.variant_id === variantId),
    [compareCart]
  );

  const addDocument = useCallback((doc) => {
    setMyDocuments((prev) => [doc, ...prev]);
  }, []);

  const removeDocument = useCallback((docId) => {
    setMyDocuments((prev) => prev.filter((doc) => doc.doc_id !== docId));
  }, []);

  return (
    <AppContext.Provider
      value={{
        addDocument,
        addToCompare,
        chatContext,
        clearCompare,
        compareCart,
        isInCompare,
        myDocuments,
        removeDocument,
        removeFromCompare,
        setChatContext,
        setMyDocuments,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);

  if (!context) {
    throw new Error("useApp must be used within AppProvider");
  }

  return context;
}
