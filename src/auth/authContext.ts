import { createContext } from "react";

export type AuthContextValue = {
  isAdmin: boolean;
  isLoading: boolean;
  userEmail: string | null;
  signInWithGoogle: (redirectPath?: string) => Promise<void>;
  signOut: () => Promise<void>;
};

export const AuthContext = createContext<AuthContextValue | null>(null);
