import { useEffect, useState } from 'react';
import type { DocumentDto } from '../types';

/** Where the simulated document list is kept in the visitor's browser. */
const DOCS_STORAGE_KEY = 'anonymiq_docs';

/** The pre-rename key, still read once so existing visitors keep their list. */
const LEGACY_DOCS_STORAGE_KEY = 'openAnonymiser_docs';

/**
 * The uploaded documents, kept in localStorage because the API has no
 * endpoint that lists them. New uploads go first.
 */
export function useStoredDocuments() {
  const [documents, setDocuments] = useState<DocumentDto[]>([]);

  useEffect(() => {
    // Read the new key, then the pre-rename one. The key lives in the
    // VISITOR's browser, not in this repo, so renaming it without a fallback
    // would not error — getItem() would just return null and every existing
    // user would silently open an empty document list. Anything found under
    // the old key is written back under the new one below, so the fallback
    // stops being needed once a user has loaded the page again.
    const storedDocs =
      localStorage.getItem(DOCS_STORAGE_KEY) ??
      localStorage.getItem(LEGACY_DOCS_STORAGE_KEY);
    if (storedDocs) {
      try {
        setDocuments(JSON.parse(storedDocs));
      } catch (err) {
        console.error('Failed to parse stored documents', err);
      }
    }
  }, []);

  useEffect(() => {
    if (documents.length > 0) {
      localStorage.setItem(DOCS_STORAGE_KEY, JSON.stringify(documents));
    }
  }, [documents]);

  const addDocuments = (newDocs: DocumentDto[]) => {
    setDocuments(prev => [...newDocs, ...prev]);
  };

  return { documents, addDocuments };
}
