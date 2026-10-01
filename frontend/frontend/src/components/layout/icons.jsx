// Minimal 18x18 stroke icons, no external icon library needed.
const common = {
  width: 18,
  height: 18,
  viewBox: '0 0 18 18',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.5,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
};

export const DashboardIcon = () => (
  <svg {...common}>
    <rect x="2" y="2" width="6" height="6" rx="1" />
    <rect x="10" y="2" width="6" height="6" rx="1" />
    <rect x="2" y="10" width="6" height="6" rx="1" />
    <rect x="10" y="10" width="6" height="6" rx="1" />
  </svg>
);

export const PartyIcon = () => (
  <svg {...common}>
    <circle cx="6.5" cy="6" r="2.5" />
    <path d="M2 15c0-2.5 2-4 4.5-4s4.5 1.5 4.5 4" />
    <circle cx="13" cy="5.5" r="2" />
    <path d="M11.5 7.2c1.9.3 3.5 1.6 3.5 3.8" />
  </svg>
);

export const CustomerIcon = () => (
  <svg {...common}>
    <circle cx="9" cy="6" r="3" />
    <path d="M3 16c0-3.3 2.7-6 6-6s6 2.7 6 6" />
  </svg>
);

export const ItemIcon = () => (
  <svg {...common}>
    <path d="M2.5 5.5 9 2l6.5 3.5L9 9 2.5 5.5Z" />
    <path d="M2.5 5.5V12.5L9 16l6.5-3.5V5.5" />
    <path d="M9 9V16" />
  </svg>
);

export const PurchaseIcon = () => (
  <svg {...common}>
    <circle cx="6" cy="15.5" r="1.2" />
    <circle cx="13" cy="15.5" r="1.2" />
    <path d="M1.5 2h2l1.7 9.2a1.5 1.5 0 0 0 1.5 1.3h6.4a1.5 1.5 0 0 0 1.5-1.2L16 5.5H4.3" />
    <path d="M9 5.5v4M7 7.5h4" />
  </svg>
);

export const SalesIcon = () => (
  <svg {...common}>
    <circle cx="6" cy="15.5" r="1.2" />
    <circle cx="13" cy="15.5" r="1.2" />
    <path d="M1.5 2h2l1.7 9.2a1.5 1.5 0 0 0 1.5 1.3h6.4a1.5 1.5 0 0 0 1.5-1.2L16 5.5H4.3" />
    <path d="M7 7.5h4" />
  </svg>
);

export const BillHistoryIcon = () => (
  <svg {...common}>
    <path d="M4 2.5h10v13l-2-1.3-1.5 1.3L9 14.2l-1.5 1.3L6 14.2l-2 1.3v-13Z" />
    <path d="M6.5 6h5M6.5 9h5" />
  </svg>
);

export const PurchaseHistoryIcon = () => (
  <svg {...common}>
    <rect x="2.5" y="2" width="9.5" height="13" rx="1" />
    <path d="M5 5.5h4.5M5 8.5h4.5M5 11.5h2.5" />
    <circle cx="13.2" cy="12.8" r="3.3" fill="var(--color-surface)" />
    <path d="M13.2 11v1.8l1.2.8" />
  </svg>
);

export const ReportsIcon = () => (
  <svg {...common}>
    <path d="M2.5 15.5V3.5" />
    <rect x="4.5" y="9" width="2.5" height="6.5" />
    <rect x="8.5" y="5.5" width="2.5" height="10" />
    <rect x="12.5" y="7.5" width="2.5" height="8" />
  </svg>
);

export const RojmelIcon = () => (
  <svg {...common}>
    <path d="M4 2.5h10v13H4z" />
    <path d="M6.5 6h5M6.5 9h5M6.5 12h3" />
  </svg>
);

export const ChevronLeftIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 3 5 8l5 5" />
  </svg>
);

export const BellIcon = () => (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4.5 7.5a4.5 4.5 0 0 1 9 0c0 3 1 4 1.5 4.5H3c.5-.5 1.5-1.5 1.5-4.5Z" />
    <path d="M7.5 14.5a1.5 1.5 0 0 0 3 0" />
  </svg>
);

export const SettingsIcon = () => (
  <svg {...common}>
    <circle cx="9" cy="9" r="2.3" />
    <path d="M9 2.5v1.6M9 13.9v1.6M15.5 9h-1.6M4.1 9H2.5M13.3 4.7l-1.1 1.1M5.8 12.1l-1.1 1.1M13.3 13.3l-1.1-1.1M5.8 5.9 4.7 4.8" />
  </svg>
);
