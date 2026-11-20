import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { api } from '../lib/api';
import { downloadBlob } from '../lib/utils/download';
import { useBusyAction, useFileChoice } from '../hooks/use-file-choice';

export function DeanonymizeForm() {
  const choice = useFileChoice();
  const busy = useBusyAction(choice.setError);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const file = choice.requireFile();
    if (!file) return;
    await busy.run(async () => {
      downloadBlob(await api.deanonymizeDocument(file), `deanonymized_${file.name}`);
      setSuccess(true);
    }, 'Deanonymization failed');
  };

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle>Deanonymize Document</CardTitle>
      </CardHeader>
      <CardContent>
        {success ? (
          <div className="p-4 border border-green-200 bg-green-50 rounded-md">
            <p className="text-green-700">Document successfully deanonymized and downloaded!</p>
          </div>
        ) : (
          <DeanonymizeFields choice={choice} isLoading={busy.isLoading} onSubmit={handleSubmit} />
        )}
      </CardContent>
    </Card>
  );
}

interface DeanonymizeFieldsProps {
  choice: ReturnType<typeof useFileChoice>;
  isLoading: boolean;
  onSubmit: (e: React.FormEvent) => void;
}

function DeanonymizeFields({ choice, isLoading, onSubmit }: DeanonymizeFieldsProps) {
  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div>
        <Input type="file" onChange={choice.onFileChange} accept=".pdf" disabled={isLoading} />
        <p className="mt-1 text-xs text-gray-500">
          Upload a previously anonymized PDF document
        </p>
      </div>
      {choice.error && <p className="text-red-500 text-sm">{choice.error}</p>}
      <Button type="submit" disabled={isLoading || !choice.file}>
        {isLoading ? 'Processing...' : 'Deanonymize Document'}
      </Button>
    </form>
  );
}
