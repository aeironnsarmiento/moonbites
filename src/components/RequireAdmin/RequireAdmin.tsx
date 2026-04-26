import { Spinner, Stack, Text } from "@chakra-ui/react";
import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";

import { useAuth } from "../../hooks/useAuth";

export function RequireAdmin({ children }: { children: ReactNode }) {
  const location = useLocation();
  const { isAdmin, isLoading } = useAuth();

  if (isLoading) {
    return (
      <Stack align="center" py={16}>
        <Spinner size="xl" color="brand.600" />
        <Text color="gray.500">Checking access…</Text>
      </Stack>
    );
  }

  if (!isAdmin) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}
