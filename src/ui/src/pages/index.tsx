import { Link, useNavigate } from 'react-router-dom';
import { DocumentUpload } from '../components/document-upload';
import { DocumentCard } from '../components/document-card';
import { Layout } from '../components/layout';
import { Button } from '../components/ui/button';
import { useStoredDocuments } from '../hooks/use-stored-documents';
import type { DocumentDto } from '../types';

export default function HomePage() {
  const { documents, addDocuments } = useStoredDocuments();
  const navigate = useNavigate();

  return (
    <Layout>
      <section className="space-y-8">
        <PageIntro />
        <ActionRow onUploadSuccess={addDocuments} />
      </section>
      <DocumentList
        documents={documents}
        onView={(id) => navigate(`/document/${id}`)}
        onAnonymize={(id) => navigate(`/document/anonymize/${id}`)}
      />
    </Layout>
  );
}

function ActionRow({ onUploadSuccess }: { onUploadSuccess: (documents: DocumentDto[]) => void }) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 lg:gap-8 items-start">
      <div className="order-2 lg:order-1">
        <DeanonymizeTeaser />
      </div>
      <div className="order-1 lg:order-2">
        <DocumentUpload onUploadSuccess={onUploadSuccess} />
      </div>
    </div>
  );
}

function PageIntro() {
  return (
    <div>
      <h2 className="text-3xl font-bold tracking-tight mb-3">Document Management</h2>
      <p className="text-gray-600 leading-relaxed text-base xl:text-lg max-w-4xl">
        Upload documents for anonymization or deanonymize previously processed documents.
      </p>
    </div>
  );
}

function DeanonymizeTeaser() {
  return (
    <div className="rounded-lg border bg-white shadow-sm h-full p-4 sm:p-6 flex flex-col justify-between">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xl font-semibold">Deanonymize</h3>
        <Link to="/deanonymize" className="hidden sm:block">
          <Button variant="outline">Deanonymize</Button>
        </Link>
      </div>
      <p className="text-gray-600 text-sm sm:text-base mb-4">
        Upload a previously anonymized document to restore the original content.
      </p>
      <Link to="/deanonymize" className="sm:hidden mt-auto">
        <Button variant="outline" className="w-full">Deanonymize Document</Button>
      </Link>
    </div>
  );
}

interface DocumentListProps {
  documents: DocumentDto[];
  onView: (id: string) => void;
  onAnonymize: (id: string) => void;
}

function DocumentList({ documents, onView, onAnonymize }: DocumentListProps) {
  return (
    <section className="pt-4">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold tracking-tight">Your Documents</h2>
        {documents.length > 0 && (
          <span className="text-xs sm:text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
            {documents.length} uploaded
          </span>
        )}
      </div>
      {documents.length === 0 ? <EmptyList /> : (
        <DocumentGrid documents={documents} onView={onView} onAnonymize={onAnonymize} />
      )}
    </section>
  );
}

function DocumentGrid({ documents, onView, onAnonymize }: DocumentListProps) {
  return (
    <div className="grid gap-4 lg:gap-5" style={{gridTemplateColumns: 'repeat(auto-fill, minmax(min(280px, 100%), 1fr))'}}>
      {documents.map(doc => (
        <DocumentCard key={doc.id} document={doc} onViewClick={onView} onAnonymizeClick={onAnonymize} />
      ))}
    </div>
  );
}

function EmptyList() {
  return (
    <div className="rounded-md border border-dashed bg-white p-12 text-center text-gray-500 text-sm">
      <p className="mb-2">No documents uploaded yet</p>
      <p className="text-xs text-gray-400">Use the upload form above to get started</p>
    </div>
  );
}
