// ProtectedRoute — gates the entire app shell on a valid session.
//
// Three states:
//   loading   → spinner
//   user      → render children
//   no user   → redirect to /login

import React, { useEffect } from "react";
import { useUser } from "./AuthContext";

export default function ProtectedRoute({ children }) {
  const { user, loading } = useUser();

  useEffect(() => {
    if (!loading && !user && typeof window !== "undefined") {
      window.location.replace("/login");
    }
  }, [user, loading]);

  if (loading) {
    return (
      <div
        className="min-h-screen flex items-center justify-center bg-brand-dark"
        data-testid="auth-loading"
      >
        <div className="w-8 h-8 border-2 border-brand-turquoise border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) {
    // Redirect kicked off in effect — render nothing to avoid flash
    return null;
  }

  return children;
}
