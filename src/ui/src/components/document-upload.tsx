import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import type { DocumentDto } from "../types";
import { api } from "../lib/api";
import { useBusyAction, useFileChoice } from '../hooks/use-file-choice';

interface DocumentUploadProps {
  onUploadSuccess: (documents: DocumentDto[]) => void;
}

export function DocumentUpload({ onUploadSuccess }: DocumentUploadProps) {
  const { choice, busy, tags, setTags, handleSubmit } = useDocumentUpload(onUploadSuccess);

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="flex-none">
        <CardTitle>Upload Document</CardTitle>
      </CardHeader>
      <CardContent className="flex-grow">
        <form onSubmit={handleSubmit} className="space-y-3 sm:space-y-4">
          <FileField choice={choice} isLoading={busy.isLoading} />
          <TagsField tags={tags} onTagsChange={setTags} isLoading={busy.isLoading} />
          {choice.error && <p className="text-red-500 text-xs sm:text-sm">{choice.error}</p>}
          <Button type="submit" disabled={busy.isLoading} className="w-full sm:w-auto">
            {busy.isLoading ? 'Uploading...' : 'Upload Document'}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

/** The upload form's file, tags and busy state, and its submit handler. */
function useDocumentUpload(onUploadSuccess: (documents: DocumentDto[]) => void) {
  const choice = useFileChoice();
  const busy = useBusyAction(choice.setError);
  const [tags, setTags] = useState<string>('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const file = choice.requireFile();
    if (!file) return;
    await busy.run(async () => {
      onUploadSuccess(await api.uploadDocument(file, parseTags(tags)));
      choice.setFile(null);
      setTags('');
      clearFileInput();
    }, 'Upload failed');
  };

  return { choice, busy, tags, setTags, handleSubmit };
}

/** The comma separated tags, trimmed, without empty ones. */
function parseTags(tags: string): string[] {
  return tags.split(',').map(tag => tag.trim()).filter(Boolean);
}

/** Empty the file input after a successful upload. */
function clearFileInput(): void {
  const fileInput = document.querySelector('input[type=file]') as HTMLInputElement;
  if (fileInput) fileInput.value = '';
}

interface FileFieldProps {
  choice: ReturnType<typeof useFileChoice>;
  isLoading: boolean;
}

function FileField({ choice, isLoading }: FileFieldProps) {
  return (
    <div>
      <Input type="file" onChange={choice.onFileChange} accept=".pdf" disabled={isLoading} className="w-full" />
      <p className="mt-1 text-xs text-gray-500">Only PDF files are supported</p>
    </div>
  );
}

interface TagsFieldProps {
  tags: string;
  onTagsChange: (tags: string) => void;
  isLoading: boolean;
}

function TagsField({ tags, onTagsChange, isLoading }: TagsFieldProps) {
  return (
    <div>
      <label htmlFor="tags" className="block text-xs sm:text-sm font-medium mb-1">
        Tags (comma separated)
      </label>
      <Input
        id="tags"
        value={tags}
        onChange={(e) => onTagsChange(e.target.value)}
        placeholder="personal, financial, medical"
        disabled={isLoading}
        className="w-full"
      />
    </div>
  );
}
