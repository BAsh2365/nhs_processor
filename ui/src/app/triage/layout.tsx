import DashboardShell from "@/components/dashboard-shell";

export default function TriageLayout({ children }: { children: React.ReactNode }) {
  return <DashboardShell>{children}</DashboardShell>;
}
