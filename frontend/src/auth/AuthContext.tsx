import { createContext, useState, useEffect, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { AuthContext } from "./AuthContextValue";
import { apiRequest, login as apiLogin, setToken, clearToken, getToken, type User, type TokenResponse } from "@/api/client";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const initAuth = async () => {
      const token = getToken();
      if (token) {
        try {
          const userData = await apiRequest<User>("/auth/me");
          setUser(userData);
        } catch {
          clearToken();
        }
      }
      setIsLoading(false);
    };
    initAuth();
  }, []);

  const login = async (email: string, password: string) => {
    const tokenResponse: TokenResponse = await apiLogin(email, password);
    setToken(tokenResponse.access_token);
    const userData = await apiRequest<User>("/auth/me");
    setUser(userData);
    navigate("/candidates");
  };

  const logout = () => {
    clearToken();
    setUser(null);
    navigate("/login");
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}