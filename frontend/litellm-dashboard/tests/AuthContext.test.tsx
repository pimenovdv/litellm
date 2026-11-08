import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { AuthProvider, useAuth } from "../src/contexts/AuthContext";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const queryClient = new QueryClient();

const TestComponent = () => {
  const { token, userRole } = useAuth();
  return (
    <div>
      <span data-testid="token">{token || "no-token"}</span>
      <span data-testid="role">{userRole || "no-role"}</span>
    </div>
  );
};

describe("AuthContext", () => {
  it("provides default auth values", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      </QueryClientProvider>
    );
    expect(screen.getByTestId("token").textContent).toBe("no-token");
    expect(screen.getByTestId("role").textContent).toBe("no-role");
  });
});
