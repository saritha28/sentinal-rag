/**
 * NextAuth.js v5 (Auth.js) configuration bound to Keycloak.
 *
 * Production: NextAuth.js issues a session backed by a Keycloak OIDC flow.
 * The backend FastAPI accepts the same access token directly (Keycloak JWKS).
 *
 * Local dev: if AUTH_DEV_BYPASS=true, we expose a credentials provider that
 * mints a session using the dev token. The backend dev-token bypass is the
 * other half of this — both flags must be aligned (CLAUDE.md "Local dev").
 */

import type { NextAuthConfig } from 'next-auth';
import NextAuth from 'next-auth';
import Credentials from 'next-auth/providers/credentials';
import Keycloak from 'next-auth/providers/keycloak';

const useDevBypass = process.env.AUTH_DEV_BYPASS === 'true';

const providers: NextAuthConfig['providers'] = [];

if (useDevBypass) {
  providers.push(
    Credentials({
      id: 'dev',
      name: 'Local dev token',
      credentials: { email: { label: 'Email', type: 'email' } },
      authorize: async (credentials) => {
        const email = (credentials?.email as string | undefined) ?? 'demo-admin@sentinelrag.local';
        return {
          id: 'dev-user',
          email,
          name: 'Local Dev',
        };
      },
    }),
  );
} else if (process.env.KEYCLOAK_ISSUER && process.env.KEYCLOAK_CLIENT_ID) {
  providers.push(
    Keycloak({
      clientId: process.env.KEYCLOAK_CLIENT_ID,
      clientSecret: process.env.KEYCLOAK_CLIENT_SECRET ?? '',
      issuer: process.env.KEYCLOAK_ISSUER,
    }),
  );
}

export const authConfig: NextAuthConfig = {
  providers,
  session: { strategy: 'jwt' },
  callbacks: {
    async jwt({ token, account }) {
      // Persist the Keycloak access token so server actions can forward it.
      if (account?.access_token) {
        token.accessToken = account.access_token;
      }
      if (useDevBypass && !token.accessToken) {
        token.accessToken = process.env.NEXT_PUBLIC_DEV_TOKEN ?? 'dev';
      }
      return token;
    },
    async session({ session, token }) {
      (session as typeof session & { accessToken?: string }).accessToken =
        (token.accessToken as string | undefined) ?? undefined;
      return session;
    },
  },
  pages: {
    signIn: '/login',
  },
};

export const { handlers, auth, signIn, signOut } = NextAuth(authConfig);
