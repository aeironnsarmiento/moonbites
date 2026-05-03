import { useCallback, useState } from "react";

export function useConfirmDialog() {
  const [isOpen, setIsOpen] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  const open = useCallback(() => {
    setIsOpen(true);
  }, []);

  const close = useCallback(() => {
    setIsOpen((current) => (isProcessing ? current : false));
  }, [isProcessing]);

  const confirm = useCallback(async <T>(asyncFn: () => Promise<T>) => {
    setIsProcessing(true);

    try {
      const result = await asyncFn();
      setIsOpen(false);
      return result;
    } finally {
      setIsProcessing(false);
    }
  }, []);

  return {
    isOpen,
    isProcessing,
    open,
    close,
    confirm,
  };
}
