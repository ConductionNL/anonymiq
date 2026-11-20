import { useNavigate } from 'react-router-dom';
import { DocumentCardHeader } from './document-card-header';
import { Layout } from './layout';
import { BackButton } from './page-states';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Card, CardContent } from './ui/card';
import { formatDate, groupPiiEntitiesByType } from '../lib/utils';
import type { DocumentDto, DocumentTagDto, PiiEntityDto } from '../types';

/** The detailed view of a document: metadata, tags and every PII entity. */
export function DocumentDetails({ document }: { document: DocumentDto }) {
  const navigate = useNavigate();

  return (
    <Layout>
      <BackButton onClick={() => navigate(`/document/${document.id}`)}>Back to Document</BackButton>
      <Card className="w-full">
        <DocumentCardHeader document={document} />
        <CardContent>
          <div className="space-y-6">
            <MetadataGrid document={document} />
            {document.tags.length > 0 && <DetailTags tags={document.tags} />}
            <PiiEntityTables entities={document.pii_entities} />
            <AnonymizeAction onClick={() => navigate(`/document/anonymize/${document.id}`)} />
          </div>
        </CardContent>
      </Card>
    </Layout>
  );
}

function AnonymizeAction({ onClick }: { onClick: () => void }) {
  return (
    <div className="flex justify-end mt-3 sm:mt-4">
      <Button onClick={onClick} className="w-full sm:w-auto">
        Anonymize Document
      </Button>
    </div>
  );
}

/** Label, value, value class and optional wrapper class of each metadata field. */
function metadataFields(document: DocumentDto): [string, string, string, string?][] {
  return [
    ['Document ID', document.id, 'font-mono text-xs break-all'],
    ['Filename', document.filename, 'text-xs'],
    ['Content Type', document.content_type, 'text-xs'],
    ['Uploaded At', formatDate(document.uploaded_at), 'text-xs'],
    ['PII Entities Count', `${document.pii_entities.length} entities detected`, 'text-xs', 'sm:col-span-2'],
  ];
}

function MetadataGrid({ document }: { document: DocumentDto }) {
  return (
    <div>
      <h3 className="text-lg font-medium mb-2">Document Metadata</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3 bg-gray-50 rounded-md">
        {metadataFields(document).map(([label, value, valueClass, wrapperClass]) => (
          <div key={label} className={wrapperClass}>
            <p className="text-sm font-medium text-gray-600">{label}</p>
            <p className={valueClass}>{value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function DetailTags({ tags }: { tags: DocumentTagDto[] }) {
  return (
    <div>
      <h3 className="text-lg font-medium mb-2">Document Tags</h3>
      <div className="flex flex-wrap gap-2">
        {tags.map(tag => (
          <Badge key={tag.id} variant="secondary" className="px-3 py-1 text-sm">
            {tag.name}
          </Badge>
        ))}
      </div>
    </div>
  );
}

function PiiEntityTables({ entities }: { entities: PiiEntityDto[] }) {
  return (
    <div>
      <h3 className="text-lg font-medium mb-2">Detected PII Entities</h3>
      {entities.length === 0 ? (
        <p className="text-gray-500 text-sm">No PII entities detected</p>
      ) : (
        <div className="space-y-4 overflow-x-auto">
          {Object.entries(groupPiiEntitiesByType(entities)).map(([type, group]) => (
            <PiiEntityTable key={type} type={type} entities={group} />
          ))}
        </div>
      )}
    </div>
  );
}

function PiiEntityTable({ type, entities }: { type: string; entities: PiiEntityDto[] }) {
  return (
    <div className="border rounded-md p-3">
      <h4 className="font-medium text-base mb-2">{type}</h4>
      <table className="w-full text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="text-left p-2">Text</th>
            <th className="text-left p-2">Position</th>
            <th className="text-left p-2">Confidence</th>
          </tr>
        </thead>
        <tbody>
          {entities.map((entity, idx) => <PiiEntityRow key={idx} entity={entity} />)}
        </tbody>
      </table>
    </div>
  );
}

function PiiEntityRow({ entity }: { entity: PiiEntityDto }) {
  return (
    <tr className="border-t">
      <td className="p-2 font-mono text-xs break-all">{entity.text}</td>
      <td className="p-2 text-xs">{entity.start}-{entity.end}</td>
      <td className="p-2 text-xs">{formatScore(entity.score)}</td>
    </tr>
  );
}

/** A score as a percentage with one decimal, or N/A without one. */
function formatScore(score: number | undefined): string {
  return score !== undefined ? `${(score * 100).toFixed(1)}%` : 'N/A';
}
