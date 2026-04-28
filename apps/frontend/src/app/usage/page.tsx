import { PageHeader } from '@/components/layout/page-header';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function UsagePage() {
  return (
    <div>
      <PageHeader
        title="Usage & Cost"
        description="Per-tenant token and cost accounting through the LiteLLM gateway."
      />
      <Card>
        <CardHeader>
          <CardTitle>Coming in Phase 6</CardTitle>
          <CardDescription>
            Cost dashboards (per-tenant budgets, soft/hard caps, model downgrade) ship with Phase 6.
            Every LLM call already double-entries into <code>usage_records</code> via the
            orchestrator — the visualization is what's left.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          The raw rows are queryable today via the API once the <code>/usage</code> route is opened
          up.
        </CardContent>
      </Card>
    </div>
  );
}
