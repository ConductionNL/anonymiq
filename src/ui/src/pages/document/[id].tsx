import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { DocumentDetails } from '../../components/document-details';
import { DocumentViewer } from '../../components/document-viewer';
import { Layout } from '../../components/layout';
import { BackButton, DocumentError, LoadingDocument } from '../../components/page-states';
import { useDocument } from '../../hooks/use-document';

export default function DocumentPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { document, loading, error } = useDocument(id);

  // The detailed view is the same URL with ?view=details
  const isDetailedView = new URLSearchParams(location.search).get('view') === 'details';

  if (loading) return <LoadingDocument />;
  if (error || !document) return <DocumentError error={error} onBack={() => navigate('/')} />;
  if (isDetailedView) return <DocumentDetails document={document} />;

  return (
    <Layout>
      <BackButton onClick={() => navigate('/')}>Back to Documents</BackButton>
      <DocumentViewer
        document={document}
        onAnonymizeClick={(documentId) => navigate(`/document/anonymize/${documentId}`)}
        onViewDetailsClick={(documentId) => navigate(`/document/${documentId}?view=details`)}
      />
    </Layout>
  );
}
