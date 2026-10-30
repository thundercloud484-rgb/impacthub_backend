import Navbar from "@/components/layout/Navbar";
export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative z-[1] min-h-screen bg-transparent">
      <Navbar />
      <main className="pt-14">{children}</main>
    </div>
  );
}
