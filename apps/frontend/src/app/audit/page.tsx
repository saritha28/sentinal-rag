import { PageHeader } from '@/components/layout/page-header';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function AuditPage() {
  return (
    <div>
      <PageHeader
        title="Audit"
        description="Append-only audit events, dual-written to Postgres + S3 Object Lock."
      />
      <Card>
        <CardHeader>
          <CardTitle>Coming in Phase 6</CardTitle>
          <CardDescription>
            The audit dual-write reconciliation surface lands with Phase 6 (observability + audit
            hardening). The schema and write-path already exist on the backend — the UI is the final
            piece.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          See <code>docs/architecture/PHASE_PLAN.md</code> for the full ordering.
        </CardContent>
      </Card>
    </div>
  );
}
