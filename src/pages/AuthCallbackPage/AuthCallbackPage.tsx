import { Spinner, Stack, Text } from "@chakra-ui/react";
import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";

function safeRedirectPath(value: string | null) {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return "/";
  }

  return value;
}

export function AuthCallbackPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { isAdmin, isLoading } = useAuth();
  const nextPath = safeRedirectPath(searchParams.get("next"));

  useEffect(() => {
    if (isLoading) {
      return;
    }

    navigate(isAdmin ? nextPath : "/login", { replace: true });
  }, [isAdmin, isLoading, navigate, nextPath]);

  return (
    <Stack align="center" py={16}>
      <Spinner size="xl" color="brand.600" />
      <Text color="gray.500">Completing sign in…</Text>
    </Stack>
  );
}
