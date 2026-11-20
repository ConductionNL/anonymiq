import { useState } from 'react';

/** The file picked in a file input, with the error shown next to it. */
export function useFileChoice() {
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  /** The picked file, or null after asking for one. */
  const requireFile = () => {
    if (!file) setError('Please select a file');
    return file;
  };

  return { file, setFile, error, setError, onFileChange, requireFile };
}

/** The message of a caught error, or a fallback for anything else. */
export function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback;
}

/**
 * Run an async action with a busy flag; a failure becomes the error message.
 * The error is cleared when the action starts.
 */
export function useBusyAction(setError: (error: string | null) => void) {
  const [isLoading, setIsLoading] = useState(false);

  const run = async (action: () => Promise<void>, fallback: string) => {
    setIsLoading(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(errorMessage(err, fallback));
    } finally {
      setIsLoading(false);
    }
  };

  return { isLoading, run };
}
