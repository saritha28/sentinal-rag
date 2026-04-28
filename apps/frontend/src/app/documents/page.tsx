'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';

import { PageHeader } from '@/components/layout/page-header';
import { StatusBadge } from '@/components/layout/status-badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useApiClient } from '@/lib/use-api-client';
import { formatDateTime } from '@/lib/utils';

export default function DocumentsPage() {
  const { client } = useApiClient();
  const qc = useQueryClient();
  const [collectionId, setCollectionId] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadOk, setUploadOk] = useState<string | null>(null);

  const collections = useQuery({
    queryKey: ['collections'],
    queryFn: () => client.listCollections({ limit: 200 }),
  });

  useEffect(() => {
    if (!collectionId && collections.data?.items.length) {
      setCollectionId(collections.data.items[0].id);
    }
  }, [collectionId, collections.data]);

  const docs = useQuery({
    queryKey: ['documents', collectionId],
    queryFn: () => client.listDocuments(collectionId),
    enabled: Boolean(collectionId),
  });
  const jobs = useQuery({
    queryKey: ['ingestion-jobs', collectionId],
    queryFn: () => client.listIngestionJobs(collectionId),
    enabled: Boolean(collectionId),
    refetchInterval: 5_000,
  });

  const upload = useMutation({
    mutationFn: async (file: File) =>
      client.uploadDocument({ collection_id: collectionId, file, title: file.name }),
    onSuccess: (resp) => {
      setUploadOk(`Queued ingestion job ${resp.ingestion_job_id.slice(0, 8)}…`);
      setUploadError(null);
      void qc.invalidateQueries({ queryKey: ['documents', collectionId] });
      void qc.invalidateQueries({ queryKey: ['ingestion-jobs', collectionId] });
      if (fileInputRef.current) fileInputRef.current.value = '';
    },
    onError: (err: Error) => {
      setUploadError(err.message);
      setUploadOk(null);
    },
  });

  return (
    <div>
      <PageHeader
        title="Documents"
        description="Upload and inspect documents per collection. Ingestion runs as a Temporal workflow."
      />

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Upload</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="collection">Collection</Label>
              <select
                id="collection"
                className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm shadow-sm"
                value={collectionId}
                onChange={(e) => setCollectionId(e.target.value)}
              >
                {collections.data?.items.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
                {!collections.data?.items.length && <option value="">No collections</option>}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="file">File</Label>
              <Input
                ref={fileInputRef}
                id="file"
                type="file"
                accept=".pdf,.txt,.md,.html,.docx"
                disabled={!collectionId || upload.isPending}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) upload.mutate(file);
                }}
              />
            </div>
          </div>
          {upload.isPending && <p className="text-sm text-muted-foreground">Uploading…</p>}
          {uploadOk && <p className="text-sm text-emerald-600">{uploadOk}</p>}
          {uploadError && <p className="text-sm text-destructive">{uploadError}</p>}
        </CardContent>
      </Card>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Documents</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Title</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {docs.data?.items.map((d) => (
                <TableRow key={d.id}>
                  <TableCell className="font-medium">{d.title}</TableCell>
                  <TableCell className="text-muted-foreground">{d.mime_type ?? '—'}</TableCell>
                  <TableCell>
                    <StatusBadge status={d.status} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDateTime(d.created_at)}
                  </TableCell>
                </TableRow>
              ))}
              {!docs.data?.items.length && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    {docs.isLoading ? 'Loading…' : 'No documents in this collection.'}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Ingestion jobs</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Job</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Strategy</TableHead>
                <TableHead>Embedding model</TableHead>
                <TableHead>Chunks</TableHead>
                <TableHead>Started</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.data?.map((j) => (
                <TableRow key={j.id}>
                  <TableCell className="font-mono text-xs">{j.id.slice(0, 8)}</TableCell>
                  <TableCell>
                    <StatusBadge status={j.status} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">{j.chunking_strategy}</TableCell>
                  <TableCell className="text-muted-foreground">{j.embedding_model}</TableCell>
                  <TableCell className="text-muted-foreground">{j.chunks_created}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDateTime(j.started_at)}
                  </TableCell>
                </TableRow>
              ))}
              {!jobs.data?.length && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground">
                    No ingestion jobs.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
