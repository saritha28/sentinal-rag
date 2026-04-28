'use client';

import { useQuery } from '@tanstack/react-query';

import { PageHeader } from '@/components/layout/page-header';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useApiClient } from '@/lib/use-api-client';

export default function SettingsPage() {
  const { client, token } = useApiClient();
  const tenant = useQuery({
    queryKey: ['me', 'tenant'],
    queryFn: () => client.myTenant(),
    retry: false,
  });
  const me = useQuery({ queryKey: ['me'], queryFn: () => client.me(), retry: false });

  return (
    <div>
      <PageHeader title="Settings" description="Identity and tenant context for this session." />

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Tenant</CardTitle>
            <CardDescription>
              Bound to <code>app.current_tenant_id</code> on every request.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <div>
              <span className="text-muted-foreground">name:</span> {tenant.data?.name ?? '—'}
            </div>
            <div>
              <span className="text-muted-foreground">slug:</span>{' '}
              <code>{tenant.data?.slug ?? '—'}</code>
            </div>
            <div>
              <span className="text-muted-foreground">plan:</span> {tenant.data?.plan ?? '—'}
            </div>
            <div>
              <span className="text-muted-foreground">status:</span> {tenant.data?.status ?? '—'}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>User</CardTitle>
            <CardDescription>Resolved from the bearer token.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <div>
              <span className="text-muted-foreground">email:</span> {me.data?.email ?? '—'}
            </div>
            <div>
              <span className="text-muted-foreground">name:</span> {me.data?.full_name ?? '—'}
            </div>
            <div>
              <span className="text-muted-foreground">id:</span>{' '}
              <code className="text-xs">{me.data?.id ?? '—'}</code>
            </div>
            <div className="pt-2 text-xs text-muted-foreground">
              Auth mode: <code>{token ? 'session token' : 'dev token'}</code>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
