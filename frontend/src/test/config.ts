// A business config like GET /business/config returns, for tests.
import type { BusinessConfig } from "@/apps/shared/startup/runStartup";

export function businessConfig(overrides: Partial<BusinessConfig> = {}): BusinessConfig {
  return {
    business: {
      name: "Mama Safi Laundry",
      slug: "mamasafi",
      country: "KE",
      currency: "KES",
      timezone: "Africa/Nairobi",
      language: "en",
    },
    branding: {
      app_name: "Mama Safi",
      logo_url: "",
      primary_color: "#7A1F5C",
      accent_color: "#F2A900",
      support_phone: "+254712345678",
      whatsapp_phone: "",
      terms_url: "",
      privacy_url: "",
    },
    maintenance: { active: false, expected_return: "" },
    catalog: {
      categories: [],
      services: [],
      modifiers: [],
      vat: { registered: false, rate: "16.00", prices_include_vat: true },
    },
    ...overrides,
  };
}
