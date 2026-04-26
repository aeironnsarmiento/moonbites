import { Button, Card, CardBody, Heading, Stack, Text } from "@chakra-ui/react";
import { useState } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { StatusBanner } from "../../components/StatusBanner/StatusBanner";
import { useAuth } from "../../hooks/useAuth";
import "./LoginPage.scss";

type LocationState = {
  from?: {
    pathname?: string;
  };
};

export function LoginPage() {
  const location = useLocation();
  const { isAdmin, isLoading, signInWithGoogle } = useAuth();
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const state = location.state as LocationState | null;
  const nextPath = state?.from?.pathname ?? "/";

  if (!isLoading && isAdmin) {
    return <Navigate to={nextPath} replace />;
  }

  const handleSignIn = async () => {
    setError("");
    setIsSubmitting(true);

    try {
      await signInWithGoogle(nextPath);
    } catch (signInError) {
      setError(
        signInError instanceof Error
          ? signInError.message
          : "Unable to start Google sign-in.",
      );
      setIsSubmitting(false);
    }
  };

  return (
    <Stack align="center" py={12} className="loginPage">
      <Card className="loginPage__card">
        <CardBody>
          <Stack spacing={5}>
            <Stack spacing={2}>
              <Text color="brand.600" fontWeight="700" fontSize="sm">
                Admin
              </Text>
              <Heading size="lg">Sign in</Heading>
              <Text color="gray.600">
                Use an approved Google account to add and edit recipes.
              </Text>
            </Stack>

            <StatusBanner error={error} />

            <Button
              colorScheme="brand"
              onClick={handleSignIn}
              isLoading={isSubmitting || isLoading}
            >
              Continue with Google
            </Button>
          </Stack>
        </CardBody>
      </Card>
    </Stack>
  );
}
