import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { DocumentUpload } from '../components/document-upload';
import { DocumentCard } from '../components/document-card';
import { Layout } from '../components/layout';
import { Button } from '../components/ui/button';
import type { DocumentDto } from '../types';

/** Where the simulated document list is kept in the visitor's browser. */
const DOCS_STORAGE_KEY = 'anonymiq_docs';

/** The pre-rename key, still read once so existing visitors keep their list. */
const LEGACY_DOCS_STORAGE_KEY = 'openAnonymiser_docs';

export default function HomePage() {
  const [documents, setDocuments] = useState<DocumentDto[]>([]);
  const navigate = useNavigate();
  
  // In a real app, we'd fetch the documents from the API
  // Since there's no endpoint for listing documents, we'll use localStorage to simulate
  useEffect(() => {
    // Read the new key, then the pre-rename one. The key lives in the
    // VISITOR's browser, not in this repo, so renaming it without a fallback
    // would not error — getItem() would just return null and every existing
    // user would silently open an empty document list. Anything found under
    // the old key is written back under the new one below, so the fallback
    // stops being needed once a user has loaded the page again.
    const storedDocs =
      localStorage.getItem(DOCS_STORAGE_KEY) ??
      localStorage.getItem(LEGACY_DOCS_STORAGE_KEY);
    if (storedDocs) {
      try {
        setDocuments(JSON.parse(storedDocs));
      } catch (err) {
        console.error('Failed to parse stored documents', err);
      }
    }
  }, []);

  // Save documents to localStorage when they change
  useEffect(() => {
    if (documents.length > 0) {
      localStorage.setItem(DOCS_STORAGE_KEY, JSON.stringify(documents));
    }
  }, [documents]);
  
  const handleUploadSuccess = (newDocs: DocumentDto[]) => {
    setDocuments(prev => [...newDocs, ...prev]);
  };
  
  const handleViewDocument = (id: string) => {
    navigate(`/document/${id}`);
  };
  
  const handleAnonymizeDocument = (id: string) => {
    navigate(`/document/anonymize/${id}`);
  };

  return (
    <Layout>
      <section className="space-y-8">
        <div>
          <h2 className="text-3xl font-bold tracking-tight mb-3">Document Management</h2>
          <p className="text-gray-600 leading-relaxed text-base xl:text-lg max-w-4xl">
            Upload documents for anonymization or deanonymize previously processed documents.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 lg:gap-8 items-start">
          <div className="order-2 lg:order-1">
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
          </div>
          <div className="order-1 lg:order-2">
            <DocumentUpload onUploadSuccess={handleUploadSuccess} />
          </div>
        </div>
      </section>

      <section className="pt-4">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold tracking-tight">Your Documents</h2>
          {documents.length > 0 && (
            <span className="text-xs sm:text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
              {documents.length} uploaded
            </span>
          )}
        </div>
        
        {documents.length === 0 ? (
          <div className="rounded-md border border-dashed bg-white p-12 text-center text-gray-500 text-sm">
            <p className="mb-2">No documents uploaded yet</p>
            <p className="text-xs text-gray-400">Use the upload form above to get started</p>
          </div>
        ) : (
          <div className="grid gap-4 lg:gap-5" style={{gridTemplateColumns: 'repeat(auto-fill, minmax(min(280px, 100%), 1fr))'}}>
            {documents.map(doc => (
              <DocumentCard 
                key={doc.id}
                document={doc}
                onViewClick={handleViewDocument}
                onAnonymizeClick={handleAnonymizeDocument}
              />
            ))}
          </div>
        )}
      </section>
    </Layout>
  );
}
