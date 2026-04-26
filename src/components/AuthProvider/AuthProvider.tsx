import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Session } from "@supabase/supabase-js";

import { AuthContext, type AuthContextValue } from "../../auth/authContext";
import { buildApiUrl } from "../../services/apiClient";
import { getSupabaseClient } from "../../services/supabaseClient";

async function fetchAdminEmail(accessToken: string): Promise<string | null> {
  const response = await fetch(buildApiUrl("/api/auth/me"), {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    return null;
  }

  const data = (await response.json().catch(() => null)) as {
    email?: unknown;
  } | null;

  return typeof data?.email === "string" ? data.email : null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const supabase = getSupabaseClient();
  const [isLoading, setIsLoading] = useState(Boolean(supabase));
  const [userEmail, setUserEmail] = useState<string | null>(null);

  const applySession = useCallback(async (session: Session | null) => {
    if (!session?.access_token) {
      setUserEmail(null);
      return;
    }

    setUserEmail(await fetchAdminEmail(session.access_token));
  }, []);

  useEffect(() => {
    let active = true;

    if (!supabase) {
      return () => {
        active = false;
      };
    }

    supabase.auth.getSession().then(async ({ data }) => {
      if (!active) {
        return;
      }

      await applySession(data.session);
      if (active) {
        setIsLoading(false);
      }
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      void applySession(session);
    });

    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, [applySession, supabase]);

  const signInWithGoogle = useCallback(async (redirectPath = "/") => {
    if (!supabase) {
      throw new Error("Supabase Auth is not configured.");
    }

    const callbackUrl = new URL("/auth/callback", window.location.origin);
    callbackUrl.searchParams.set("next", redirectPath);

    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: callbackUrl.toString(),
      },
    });

    if (error) {
      throw error;
    }
  }, [supabase]);

  const signOut = useCallback(async () => {
    if (!supabase) {
      setUserEmail(null);
      return;
    }

    await supabase.auth.signOut();
    setUserEmail(null);
  }, [supabase]);

  const value = useMemo<AuthContextValue>(
    () => ({
      isAdmin: Boolean(userEmail),
      isLoading,
      userEmail,
      signInWithGoogle,
      signOut,
    }),
    [isLoading, signInWithGoogle, signOut, userEmail],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
