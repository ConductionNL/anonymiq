import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Checkbox } from './ui/checkbox';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { groupPiiEntitiesByType } from '../lib/utils';
import { api } from '../lib/api';
import type { DocumentDto } from '../types';

interface AnonymizationFormProps {
  document: DocumentDto;
  onComplete: () => void;
}

export function AnonymizationForm({ document, onComplete }: AnonymizationFormProps) {
  const [selectedEntityTypes, setSelectedEntityTypes] = useState<string[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [anonymizationResult, setAnonymizationResult] = useState<{
    status: string;
    time_taken: number;
  } | null>(null);
  
  const piiGroups = groupPiiEntitiesByType(document.pii_entities);
  
  const handleCheck = (entityType: string) => {
    if (selectedEntityTypes.includes(entityType)) {
      setSelectedEntityTypes(selectedEntityTypes.filter(type => type !== entityType));
    } else {
      setSelectedEntityTypes([...selectedEntityTypes, entityType]);
    }
  };
  
  const isSelected = (entityType: string) => {
    return selectedEntityTypes.includes(entityType);
  };
  
  const handleAnonymize = async () => {
    if (selectedEntityTypes.length === 0) {
      setError('Please select at least one entity type to anonymize');
      return;
    }
    
    setIsProcessing(true);
    setError(null);
    
    try {
      // Pass the selected entity types directly to the API
      const result = await api.anonymizeDocument(document.id, selectedEntityTypes);
      setAnonymizationResult({
        status: result.status,
        time_taken: result.time_taken
      });
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Anonymization failed');
    } finally {
      setIsProcessing(false);
    }
  };
  
  const handleDownload = async () => {
    try {
      window.location.href = api.getDocumentDownloadUrl(document.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Download failed');
    }
  };
  
  return (
    <Card>
      <CardHeader>
        <CardTitle>Anonymize Document: {document.filename}</CardTitle>
      </CardHeader>
      <CardContent>
        {success ? (
          <div className="space-y-4">
            <div className="p-4 border border-green-200 bg-green-50 rounded-md">
              <h3 className="font-medium text-green-800">Anonymization Complete</h3>
              <p>Status: {anonymizationResult?.status}</p>
              <p>Time taken: {anonymizationResult?.time_taken}ms</p>
            </div>
            
            <div className="space-y-2">
              <h4 className="font-medium">Anonymized Entity Types:</h4>
              <div className="space-y-2">
                {selectedEntityTypes.map((entityType, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <Badge>{entityType}</Badge>
                  </div>
                ))}
              </div>
            </div>
            
            <div className="flex justify-between mt-6">
              <Button variant="outline" onClick={onComplete}>
                Back to Documents
              </Button>
              <Button onClick={handleDownload}>
                Download Anonymized Document
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-medium mb-2">Select PII Entity Types to Anonymize</h3>
              <p className="text-sm text-gray-500 mb-4">
                Choose which types of personally identifiable information should be anonymized in the document.
              </p>
              
              {Object.entries(piiGroups).length === 0 ? (
                <p className="text-gray-500">No PII entities detected in this document</p>
              ) : (
                <div className="space-y-6">
                  {Object.entries(piiGroups).map(([type, entities]) => (
                    <div key={type} className="space-y-2">
                      <div className="flex items-center gap-2">
                        <Checkbox 
                          id={`entity-type-${type}`}
                          checked={isSelected(type)}
                          onCheckedChange={() => handleCheck(type)}
                        />
                        <label 
                          htmlFor={`entity-type-${type}`} 
                          className="font-medium cursor-pointer"
                        >
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
                  ))}
                </div>
              )}
            </div>
            
            {error && (
              <div className="p-3 text-red-600 bg-red-50 border border-red-200 rounded-md">
                {error}
              </div>
            )}
            
            <div className="flex justify-between">
              <Button variant="outline" onClick={onComplete} disabled={isProcessing}>
                Cancel
              </Button>
              <Button 
                onClick={handleAnonymize} 
                disabled={isProcessing || selectedEntityTypes.length === 0}
              >
                {isProcessing ? 'Processing...' : 'Anonymize Document'}
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
