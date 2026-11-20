import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import type { DocumentDto } from '../types';

/** Load a document's metadata, with its PII entities, for the given id. */
export function useDocument(id: string | undefined) {
  const [document, setDocument] = useState<DocumentDto | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDocument = async () => {
      if (!id) return;

      try {
        setLoading(true);
        const data = await api.getDocumentMetadata(id, true);
        setDocument(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load document');
      } finally {
        setLoading(false);
      }
    };

    fetchDocument();
  }, [id]);

  return { document, loading, error };
}
