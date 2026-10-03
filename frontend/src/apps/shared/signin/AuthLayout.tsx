// The frame of the sign-in screens: the business's logo (or app name) and the title.
import type { ReactNode } from "react";

import { useBusinessConfig } from "@/apps/shared/startup/BusinessConfigContext";

export function AuthLayout({ title, children }: { title: string; children: ReactNode }) {
  const { business, branding } = useBusinessConfig();
  const name = branding.app_name || business.name;
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-sm flex-col gap-6 px-4 py-12">
      <header className="flex flex-col items-center gap-4 text-center">
        {branding.logo_url ? (
          <img src={branding.logo_url} alt={name} className="max-h-16 max-w-48 object-contain" />
        ) : (
          <p className="font-heading text-section-title text-brand-primary">{name}</p>
        )}
        <h1 className="font-heading text-page-title text-text">{title}</h1>
      </header>
      {children}
    </main>
  );
}
