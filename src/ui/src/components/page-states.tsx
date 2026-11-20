import { Layout } from './layout';
import { Button } from './ui/button';

interface BackButtonProps {
  onClick: () => void;
  children: React.ReactNode;
}

/** The outline button above a page's content that leads back. */
export function BackButton({ onClick, children }: BackButtonProps) {
  return (
    <div className="mb-4">
      <Button variant="outline" onClick={onClick}>{children}</Button>
    </div>
  );
}

/** The page shown while a document loads. */
export function LoadingDocument() {
  return (
    <Layout>
      <div className="flex justify-center items-center h-32">
        Loading document...
      </div>
    </Layout>
  );
}

interface DocumentErrorProps {
  error: string | null;
  onBack: () => void;
}

/** The page shown when a document could not be loaded. */
export function DocumentError({ error, onBack }: DocumentErrorProps) {
  return (
    <Layout>
      <BackButton onClick={onBack}>Back to Documents</BackButton>
      <div className="p-4 border border-red-300 bg-red-50 rounded-md">
        <h2 className="text-lg font-medium text-red-800 mb-2">Error</h2>
        <p>{error || 'Document not found'}</p>
      </div>
    </Layout>
  );
}
