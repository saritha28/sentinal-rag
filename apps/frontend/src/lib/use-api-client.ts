'use client';

/**
 * Hook that returns the API client bound to the current session token.
 * Outside auth (local dev with NEXT_PUBLIC_DEV_TOKEN), the client falls back
 * to the dev token automatically — but explicit binding is the right path
 * for cloud deploys.
 */

import { useSession } from 'next-auth/react';
import { useMemo } from 'react';

import { api } from './api';

type Bound = {
  [K in keyof typeof api]: (typeof api)[K];
};

export function useApiClient(): { client: Bound; token: string | undefined } {
  const { data: session } = useSession();
  const token = (session as (typeof session & { accessToken?: string }) | null)?.accessToken;

  const client = useMemo<Bound>(() => {
    // Wrap each method to inject the token as the last/last-named arg.
    // For methods that take `(payload, token?)` or options-bag with `token`,
    // we pass through and let the underlying method default-fall to dev token.
    return new Proxy(api, {
      get(target, prop: string) {
        const original = target[prop as keyof typeof api];
        if (typeof original !== 'function') return original;
        return (...args: unknown[]) => {
          // Inject token: append for trailing-token signatures, merge for opts bags.
          const last = args[args.length - 1];
          if (
            last &&
            typeof last === 'object' &&
            !(last instanceof FormData) &&
            !('byteLength' in last)
          ) {
            args[args.length - 1] = {
              ...(last as object),
              token: (last as { token?: string }).token ?? token,
            };
          } else {
            args.push(token);
          }
          // biome-ignore lint/suspicious/noExplicitAny: dynamic bind
          return (original as (...a: unknown[]) => unknown).apply(target, args as any);
        };
      },
    }) as Bound;
  }, [token]);

  return { client, token };
}
