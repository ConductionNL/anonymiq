import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Checkbox } from './ui/checkbox';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { groupPiiEntitiesByType } from '../lib/utils';
import { api } from '../lib/api';
import type { DocumentDto, PiiEntityDto } from '../types';
import { errorMessage, useBusyAction } from '../hooks/use-file-choice';

interface AnonymizationFormProps {
  document: DocumentDto;
  onComplete: () => void;
}

interface AnonymizationResult {
  status: string;
  time_taken: number;
}

export function AnonymizationForm({ document, onComplete }: AnonymizationFormProps) {
  const selection = useEntityTypeSelection();
  const run = useAnonymization(document.id, selection.selected);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Anonymize Document: {document.filename}</CardTitle>
      </CardHeader>
      <CardContent>
        {run.success ? (
          <AnonymizationComplete run={run} entityTypes={selection.selected} onComplete={onComplete} />
        ) : (
          <div className="space-y-4">
            <EntityTypeChooser entities={document.pii_entities} selection={selection} />
            {run.error && <ErrorMessage message={run.error} />}
            <ChooserActions run={run} canSubmit={selection.selected.length > 0} onCancel={onComplete} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

type EntityTypeSelection = ReturnType<typeof useEntityTypeSelection>;

/** The entity types picked for anonymization, in the order they were picked. */
function useEntityTypeSelection() {
  const [selected, setSelected] = useState<string[]>([]);
  const isSelected = (entityType: string) => selected.includes(entityType);
  const toggle = (entityType: string) => {
    if (isSelected(entityType)) {
      setSelected(selected.filter(type => type !== entityType));
    } else {
      setSelected([...selected, entityType]);
    }
  };
  return { selected, isSelected, toggle };
}

type AnonymizationRun = ReturnType<typeof useAnonymization>;

/** One anonymization request for a document, its progress and its download. */
function useAnonymization(documentId: string, entityTypes: string[]) {
  const [error, setError] = useState<string | null>(null);
  const busy = useBusyAction(setError);
  const [success, setSuccess] = useState(false);
  const [result, setResult] = useState<AnonymizationResult | null>(null);

  const start = async () => {
    if (entityTypes.length === 0) {
      setError('Please select at least one entity type to anonymize');
      return;
    }
    await busy.run(async () => {
      const response = await api.anonymizeDocument(documentId, entityTypes);
      setResult({ status: response.status, time_taken: response.time_taken });
      setSuccess(true);
    }, 'Anonymization failed');
  };

  const download = async () => {
    try {
      window.location.href = api.getDocumentDownloadUrl(documentId);
    } catch (err) {
      setError(errorMessage(err, 'Download failed'));
    }
  };

  return { isProcessing: busy.isLoading, error, success, result, start, download };
}

interface AnonymizationCompleteProps {
  run: AnonymizationRun;
  entityTypes: string[];
  onComplete: () => void;
}

function AnonymizationComplete({ run, entityTypes, onComplete }: AnonymizationCompleteProps) {
  return (
    <div className="space-y-4">
      <div className="p-4 border border-green-200 bg-green-50 rounded-md">
        <h3 className="font-medium text-green-800">Anonymization Complete</h3>
        <p>Status: {run.result?.status}</p>
        <p>Time taken: {run.result?.time_taken}ms</p>
      </div>
      <AnonymizedTypes entityTypes={entityTypes} />
      <CompleteActions onComplete={onComplete} onDownload={run.download} />
    </div>
  );
}

function CompleteActions({ onComplete, onDownload }: { onComplete: () => void; onDownload: () => void }) {
  return (
    <div className="flex justify-between mt-6">
      <Button variant="outline" onClick={onComplete}>
        Back to Documents
      </Button>
      <Button onClick={onDownload}>
        Download Anonymized Document
      </Button>
    </div>
  );
}

function AnonymizedTypes({ entityTypes }: { entityTypes: string[] }) {
  return (
    <div className="space-y-2">
      <h4 className="font-medium">Anonymized Entity Types:</h4>
      <div className="space-y-2">
        {entityTypes.map((entityType, idx) => (
          <div key={idx} className="flex items-center gap-2">
            <Badge>{entityType}</Badge>
          </div>
        ))}
      </div>
    </div>
  );
}

interface EntityTypeChooserProps {
  entities: PiiEntityDto[];
  selection: EntityTypeSelection;
}

function EntityTypeChooser({ entities, selection }: EntityTypeChooserProps) {
  const groups = Object.entries(groupPiiEntitiesByType(entities));
  return (
    <div>
      <h3 className="text-lg font-medium mb-2">Select PII Entity Types to Anonymize</h3>
      <p className="text-sm text-gray-500 mb-4">
        Choose which types of personally identifiable information should be anonymized in the document.
      </p>
      {groups.length === 0 ? (
        <p className="text-gray-500">No PII entities detected in this document</p>
      ) : (
        <div className="space-y-6">
          {groups.map(([type, group]) => (
            <EntityTypeOption key={type} type={type} entities={group} selection={selection} />
          ))}
        </div>
      )}
    </div>
  );
}

interface EntityTypeOptionProps {
  type: string;
  entities: PiiEntityDto[];
  selection: EntityTypeSelection;
}

function EntityTypeOption({ type, entities, selection }: EntityTypeOptionProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Checkbox
          id={`entity-type-${type}`}
          checked={selection.isSelected(type)}
          onCheckedChange={() => selection.toggle(type)}
        />
        <label htmlFor={`entity-type-${type}`} className="font-medium cursor-pointer">
          {type} ({entities.length})
        </label>
      </div>
      <div className="space-y-2 pl-6 border-l-2 border-gray-200">
        {entities.map((entity, idx) => (
          <div key={idx} className="text-sm text-gray-600">
            {entity.text}
          </div>
        ))}
      </div>
    </div>
  );
}

function ErrorMessage({ message }: { message: string }) {
  return (
    <div className="p-3 text-red-600 bg-red-50 border border-red-200 rounded-md">
      {message}
    </div>
  );
}

interface ChooserActionsProps {
  run: AnonymizationRun;
  canSubmit: boolean;
  onCancel: () => void;
}

function ChooserActions({ run, canSubmit, onCancel }: ChooserActionsProps) {
  return (
    <div className="flex justify-between">
      <Button variant="outline" onClick={onCancel} disabled={run.isProcessing}>
        Cancel
      </Button>
      <Button onClick={run.start} disabled={run.isProcessing || !canSubmit}>
        {run.isProcessing ? 'Processing...' : 'Anonymize Document'}
      </Button>
    </div>
  );
}
