import { Alert, AlertDescription, AlertIcon, Box } from "@chakra-ui/react";

import "./StatusBanner.scss";

type StatusBannerProps = {
  error?: string;
  status?: string;
};

export function StatusBanner({ error, status }: StatusBannerProps) {
  if (!error && !status) {
    return null;
  }

  return (
    <Box className="statusBanner">
      {error ? (
        <Alert status="error" borderRadius="18px">
          <AlertIcon />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      {!error && status ? (
        <Alert status="success" borderRadius="18px">
          <AlertIcon />
          <AlertDescription>{status}</AlertDescription>
        </Alert>
      ) : null}
    </Box>
  );
}
