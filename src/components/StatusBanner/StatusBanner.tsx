import { Alert, AlertDescription, AlertIcon, Box, Button } from "@chakra-ui/react";

import "./StatusBanner.scss";

export type StatusBannerAction = {
  label: string;
  onClick: () => void;
  isLoading?: boolean;
};

type StatusBannerProps = {
  error?: string;
  status?: string;
  /** Shows the status as in-progress (info styling, polite live region) rather than a completed success. */
  isPending?: boolean;
  /** Optional action offered alongside the error, e.g. "Resume" after an interrupted import. */
  action?: StatusBannerAction;
};

export function StatusBanner({ error, status, isPending = false, action }: StatusBannerProps) {
  if (!error && !status) {
    return null;
  }

  return (
    <Box className="statusBanner">
      {error ? (
        <Alert status="error" borderRadius="18px" role="alert">
          <AlertIcon />
          <AlertDescription>{error}</AlertDescription>
          {action ? (
            <Button
              size="sm"
              ml="auto"
              onClick={action.onClick}
              isLoading={action.isLoading}
              flexShrink={0}
            >
              {action.label}
            </Button>
          ) : null}
        </Alert>
      ) : null}
      {!error && status ? (
        <Alert
          status={isPending ? "info" : "success"}
          borderRadius="18px"
          role="status"
          aria-live="polite"
        >
          <AlertIcon />
          <AlertDescription>{status}</AlertDescription>
        </Alert>
      ) : null}
    </Box>
  );
}
