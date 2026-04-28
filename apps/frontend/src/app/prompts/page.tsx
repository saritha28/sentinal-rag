'use client';

import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { PageHeader } from '@/components/layout/page-header';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
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

export default function PromptsPage() {
  const { client } = useApiClient();
  const [selected, setSelected] = useState<string | null>(null);

  const templates = useQuery({
    queryKey: ['prompts'],
    queryFn: () => client.listPrompts(),
  });
  const versions = useQuery({
    queryKey: ['prompt-versions', selected],
    queryFn: () => client.listPromptVersions(selected as string),
    enabled: Boolean(selected),
  });

  return (
    <div>
      <PageHeader
        title="Prompts"
        description="Versioned templates. Generation persists prompt_version_id on every answer."
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Templates</CardTitle>
            <CardDescription>Click to inspect versions.</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Task type</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {templates.data?.map((t) => (
                  <TableRow
                    key={t.id}
                    className={selected === t.id ? 'bg-muted/50' : ''}
                    onClick={() => setSelected(t.id)}
                    style={{ cursor: 'pointer' }}
                  >
                    <TableCell className="font-medium">{t.name}</TableCell>
                    <TableCell className="text-muted-foreground">{t.task_type}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{t.status}</Badge>
                    </TableCell>
                  </TableRow>
                ))}
                {!templates.data?.length && (
                  <TableRow>
                    <TableCell colSpan={3} className="text-center text-muted-foreground">
                      {templates.isLoading ? 'Loading…' : 'No templates.'}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Versions</CardTitle>
            <CardDescription>
              {selected ? 'Latest first.' : 'Select a template to view its history.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Version</TableHead>
                  <TableHead>Default</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {versions.data?.map((v) => (
                  <TableRow key={v.id}>
                    <TableCell className="font-mono text-xs">v{v.version_number}</TableCell>
                    <TableCell>
                      {v.is_default ? <Badge variant="success">default</Badge> : '—'}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDateTime(v.created_at)}
                    </TableCell>
                  </TableRow>
                ))}
                {selected && !versions.data?.length && (
                  <TableRow>
                    <TableCell colSpan={3} className="text-center text-muted-foreground">
                      {versions.isLoading ? 'Loading…' : 'No versions yet.'}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
