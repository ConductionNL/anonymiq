import { Card, CardContent } from './ui/card';
import { DocumentCardHeader } from './document-card-header';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { groupPiiEntitiesByType } from '../lib/utils';
import type { DocumentDto, DocumentTagDto, PiiEntityDto } from '../types';

interface DocumentViewerProps {
  document: DocumentDto;
  onAnonymizeClick: (id: string) => void;
  onViewDetailsClick?: (id: string) => void;
}

export function DocumentViewer({ document, onAnonymizeClick, onViewDetailsClick }: DocumentViewerProps) {
  return (
    <Card className="w-full">
      <DocumentCardHeader document={document} />
      <CardContent className="space-y-3 sm:space-y-4">
        <ViewerId id={document.id} />
        {document.tags.length > 0 && <ViewerTags tags={document.tags} />}
        <ViewerEntities entities={document.pii_entities} />
        <ViewerActions
          documentId={document.id}
          onAnonymizeClick={onAnonymizeClick}
          onViewDetailsClick={onViewDetailsClick}
        />
      </CardContent>
    </Card>
  );
}

function ViewerSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-base sm:text-lg font-medium mb-1 sm:mb-2">{title}</h3>
      {children}
    </div>
  );
}

function ViewerId({ id }: { id: string }) {
  return (
    <ViewerSection title="Document Details">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 sm:gap-2 text-xs sm:text-sm">
        <span className="font-medium">ID:</span>
        <span className="font-mono break-all">{id}</span>
      </div>
    </ViewerSection>
  );
}

function ViewerTags({ tags }: { tags: DocumentTagDto[] }) {
  return (
    <ViewerSection title="Tags">
      <div className="flex flex-wrap gap-1">
        {tags.map(tag => (
          <Badge key={tag.id} variant="secondary" className="text-xs">{tag.name}</Badge>
        ))}
      </div>
    </ViewerSection>
  );
}

function ViewerEntities({ entities }: { entities: PiiEntityDto[] }) {
  return (
    <ViewerSection title="Detected PII Entities">
      {entities.length === 0 ? (
        <p className="text-gray-500 text-xs sm:text-sm">No PII entities detected</p>
      ) : (
        <div className="space-y-3 sm:space-y-4 overflow-x-auto">
          {Object.entries(groupPiiEntitiesByType(entities)).map(([type, group]) => (
            <ViewerEntityGroup key={type} type={type} entities={group} />
          ))}
        </div>
      )}
    </ViewerSection>
  );
}

function ViewerEntityGroup({ type, entities }: { type: string; entities: PiiEntityDto[] }) {
  return (
    <div className="border-b pb-2">
      <h4 className="font-medium mb-1 text-sm sm:text-base">{type}</h4>
      <ul className="list-disc list-inside space-y-1">
        {entities.map((entity, idx) => (
          <li key={idx} className="text-xs sm:text-sm break-words">
            {entity.text}
          </li>
        ))}
      </ul>
    </div>
  );
}

interface ViewerActionsProps {
  documentId: string;
  onAnonymizeClick: (id: string) => void;
  onViewDetailsClick?: (id: string) => void;
}

function ViewerActions({ documentId, onAnonymizeClick, onViewDetailsClick }: ViewerActionsProps) {
  return (
    <div className="flex justify-end mt-3 sm:mt-4 gap-2">
      {onViewDetailsClick && (
        <Button
          onClick={() => onViewDetailsClick(documentId)}
          variant="outline"
          className="w-full sm:w-auto"
        >
          View Details
        </Button>
      )}
      <Button onClick={() => onAnonymizeClick(documentId)} className="w-full sm:w-auto">
        Anonymize Document
      </Button>
    </div>
  );
}
