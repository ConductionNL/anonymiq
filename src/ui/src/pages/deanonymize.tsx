import { useNavigate } from 'react-router-dom';
import { DeanonymizeForm } from '../components/deanonymize-form';
import { Layout } from '../components/layout';
import { Button } from '../components/ui/button';

export default function DeanonymizePage() {
  const navigate = useNavigate();
  
  const handleBack = () => {
    navigate('/');
  };
  
  return (
    <Layout>
      <div className="mb-4">
        <Button variant="outline" onClick={handleBack}>Back to Documents</Button>
      </div>
      
      <DeanonymizeIntro />
      
      <DeanonymizeForm />
    </Layout>
  );
}

function DeanonymizeIntro() {
  return (
    <>
      <h2 className="text-2xl font-bold mb-4">Deanonymize Document</h2>
      <p className="text-gray-600 mb-6">
        Upload a previously anonymized document to restore the original content with 
        sensitive information.
      </p>
    </>
  );
}
