import { useParams, useNavigate } from 'react-router-dom';
import { AnonymizationForm } from '../../../components/anonymization-form';
import { Layout } from '../../../components/layout';
import { BackButton, DocumentError, LoadingDocument } from '../../../components/page-states';
import { useDocument } from '../../../hooks/use-document';

export default function AnonymizePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { document, loading, error } = useDocument(id);
  const toList = () => navigate('/');

  if (loading) return <LoadingDocument />;
  if (error || !document) return <DocumentError error={error} onBack={toList} />;

  return (
    <Layout>
      <BackButton onClick={toList}>Back to Documents</BackButton>
      <AnonymizationForm document={document} onComplete={toList} />
    </Layout>
  );
}
