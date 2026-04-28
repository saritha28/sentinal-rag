'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { PageHeader } from '@/components/layout/page-header';
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
import { Textarea } from '@/components/ui/textarea';
import type { CollectionCreate } from '@/lib/api-types';
import { useApiClient } from '@/lib/use-api-client';
import { cn, formatDateTime } from '@/lib/utils';

export default function CollectionsPage() {
  const { client } = useApiClient();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<CollectionCreate>({
    name: '',
    description: '',
    visibility: 'tenant',
  });
  const [error, setError] = useState<string | null>(null);

  const collections = useQuery({
    queryKey: ['collections'],
    queryFn: () => client.listCollections({ limit: 200 }),
  });

  const createMutation = useMutation({
    mutationFn: (payload: CollectionCreate) => client.createCollection(payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['collections'] });
      setOpen(false);
      setForm({ name: '', description: '', visibility: 'tenant' });
      setError(null);
    },
    onError: (err: Error) => setError(err.message),
  });

  return (
    <div>
      <PageHeader
        title="Collections"
        description="Logical scopes for ingestion + retrieval. RBAC is enforced per-collection."
        actions={
          <Button onClick={() => setOpen((v) => !v)}>{open ? 'Cancel' : 'New collection'}</Button>
        }
      />

      {open && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>New collection</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              className="grid gap-4 md:grid-cols-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (!form.name) {
                  setError('Name required.');
                  return;
                }
                createMutation.mutate(form);
              }}
            >
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  required
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="visibility">Visibility</Label>
                <select
                  id="visibility"
                  className={cn(
                    'h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm shadow-sm',
                  )}
                  value={form.visibility}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      visibility: e.target.value as CollectionCreate['visibility'],
                    })
                  }
                >
                  <option value="private">private</option>
                  <option value="tenant">tenant</option>
                  <option value="public">public</option>
                </select>
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={form.description ?? ''}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                />
              </div>
              {error && <div className="md:col-span-2 text-sm text-destructive">{error}</div>}
              <div className="md:col-span-2">
                <Button type="submit" disabled={createMutation.isPending}>
                  {createMutation.isPending ? 'Creating…' : 'Create collection'}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Visibility</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {collections.isLoading && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    Loading…
                  </TableCell>
                </TableRow>
              )}
              {collections.error && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-destructive">
                    {(collections.error as Error).message}
                  </TableCell>
                </TableRow>
              )}
              {collections.data?.items.map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="font-medium">{c.name}</TableCell>
                  <TableCell className="text-muted-foreground">{c.visibility}</TableCell>
                  <TableCell className="text-muted-foreground">{c.description ?? '—'}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDateTime(c.created_at)}
                  </TableCell>
                </TableRow>
              ))}
              {collections.data?.items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    No collections yet.
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
