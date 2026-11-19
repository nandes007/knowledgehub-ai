"use client";

import { createContext, useContext } from "react";
import { roleAtLeast, type MyCompany } from "@/lib/api";

type CompanyContextValue = {
  company: MyCompany;
  slug: string;
  isAdmin: boolean;
  isOwner: boolean;
};

const CompanyContext = createContext<CompanyContextValue | null>(null);

// The company named by the route's slug, with the caller's membership in it.
// Role-dependent UI reads it from here, never from the account.
export function CompanyProvider({ company, children }: { company: MyCompany; children: React.ReactNode }) {
  return (
    <CompanyContext.Provider
      value={{
        company,
        slug: company.slug,
        isAdmin: roleAtLeast(company.role, "admin"),
        isOwner: company.role === "owner",
      }}
    >
      {children}
    </CompanyContext.Provider>
  );
}

export function useCompany() {
  const ctx = useContext(CompanyContext);
  if (!ctx) throw new Error("useCompany must be used within CompanyProvider");
  return ctx;
}
