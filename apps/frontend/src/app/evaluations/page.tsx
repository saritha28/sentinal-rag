'use client';

import { useQuery } from '@tanstack/react-query';

import { PageHeader } from '@/components/layout/page-header';
import { StatusBadge } from '@/components/layout/status-badge';
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

export default function EvaluationsPage() {
  const { client } = useApiClient();
  const runs = useQuery({
    queryKey: ['eval-runs'],
    queryFn: () => client.listEvalRuns(),
  });

  return (
    <div>
      <PageHeader
        title="Evaluations"
        description="ragas + custom evaluators (faithfulness, citation accuracy) on golden datasets."
      />
      <Card>
        <CardHeader>
          <CardTitle>Recent runs</CardTitle>
          <CardDescription>
            Each run pins a prompt version, model, and dataset for reproducibility.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Run</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Started</TableHead>
                <TableHead>Completed</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.data?.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-mono text-xs">{r.id.slice(0, 8)}</TableCell>
                  <TableCell className="font-medium">{r.name}</TableCell>
                  <TableCell>
                    <StatusBadge status={r.status} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDateTime(r.started_at)}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDateTime(r.completed_at)}
                  </TableCell>
                </TableRow>
              ))}
              {!runs.data?.length && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground">
                    {runs.isLoading
                      ? 'Loading…'
                      : 'No evaluation runs yet. Trigger one via POST /api/v1/eval/runs.'}
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
