import {
  createContext,
  useContext,
  useEffect,
  useState,
} from "react";

import {
  login as loginRequest,
  register as registerRequest,
} from "../api/auth";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(
    () => localStorage.getItem("access_token")
  );

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(false);
  }, []);

  async function login(email, password) {
    const data = await loginRequest(email, password);

    localStorage.setItem("access_token", data.access_token);
    setToken(data.access_token);

    return data;
  }

  async function register(email, password) {
    return registerRequest(email, password);
  }

  function logout() {
    localStorage.removeItem("access_token");
    setToken(null);
  }

  return (
    <AuthContext.Provider
      value={{
        token,
        isAuthenticated: Boolean(token),
        loading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used inside an AuthProvider"
    );
  }

  return context;
}