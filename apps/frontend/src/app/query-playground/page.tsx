import { PageHeader } from '@/components/layout/page-header';
import { QueryForm } from '@/components/query/query-form';

export default function QueryPlaygroundPage() {
  return (
    <div>
      <PageHeader
        title="Query Playground"
        description="Run a grounded query and inspect every retrieval stage in the trace."
      />
      <QueryForm />
    </div>
  );
}
