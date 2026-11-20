import { CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { formatDate } from '../lib/utils';
import type { DocumentDto } from '../types';

/** Filename, content type and upload time at the top of a document card. */
export function DocumentCardHeader({ document }: { document: DocumentDto }) {
  return (
    <CardHeader>
      <CardTitle className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
        <span className="break-words">{document.filename}</span>
        <Badge className="whitespace-nowrap">{document.content_type}</Badge>
      </CardTitle>
      <p className="text-xs sm:text-sm text-gray-500">Uploaded: {formatDate(document.uploaded_at)}</p>
    </CardHeader>
  );
}
