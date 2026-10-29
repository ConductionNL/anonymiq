import { Header } from './header';

interface LayoutProps {
  children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen w-full flex flex-col bg-gray-50">
      <Header />
      <main className="flex-1 w-full min-w-0">
        <div className="w-full px-4 sm:px-6 lg:px-8 xl:px-12 2xl:px-16 py-6 sm:py-8 lg:py-10 space-y-12">
          {children}
        </div>
      </main>
      <footer className="w-full border-t bg-white/70 backdrop-blur supports-[backdrop-filter]:bg-white/50">
        <div className="px-4 sm:px-6 lg:px-8 xl:px-12 2xl:px-16 py-6 text-xs sm:text-sm text-gray-500 flex flex-col sm:flex-row gap-2 sm:items-center justify-between">
          <span>&copy; {new Date().getFullYear()} Anonymiq</span>
          <span className="hidden sm:inline">Secure document anonymization &amp; deanonymization. Built by Centric and Conduction.</span>
        </div>
      </footer>
    </div>
  );
}
