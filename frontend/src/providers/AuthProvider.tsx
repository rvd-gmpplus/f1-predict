"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { authApi } from "@/lib/api";
import { getToken, setToken, removeToken, hasValidToken } from "@/lib/auth";
import type { User } from "@/types";

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => void;
  handleOAuthToken: (token: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isLoading: true,
    isAuthenticated: false,
  });

  const fetchUser = useCallback(async () => {
    if (!hasValidToken()) {
      setState({ user: null, isLoading: false, isAuthenticated: false });
      return;
    }
    try {
      const user = await authApi.me();
      setState({ user, isLoading: false, isAuthenticated: true });
    } catch {
      removeToken();
      setState({ user: null, isLoading: false, isAuthenticated: false });
    }
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const login = async (email: string, password: string) => {
    const res = await authApi.login({ email, password });
    setToken(res.access_token);
    await fetchUser();
  };

  const register = async (email: string, username: string, password: string) => {
    const res = await authApi.register({ email, username, password });
    setToken(res.access_token);
    await fetchUser();
  };

  const logout = () => {
    removeToken();
    setState({ user: null, isLoading: false, isAuthenticated: false });
  };

  const handleOAuthToken = async (token: string) => {
    setToken(token);
    await fetchUser();
  };

  return (
    <AuthContext.Provider
      value={{ ...state, login, register, logout, handleOAuthToken }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuthContext() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuthContext must be used within AuthProvider");
  return ctx;
}
