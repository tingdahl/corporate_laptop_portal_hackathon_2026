export type GoogleCredentialResponse = {
  credential: string;
};

export type GoogleClient = {
  accounts: {
    id: {
      initialize: (opts: { client_id: string; callback: (resp: GoogleCredentialResponse) => void }) => void;
      renderButton: (el: HTMLElement, opts: { theme: string; size: string; shape: string }) => void;
    };
  };
};

declare global {
  interface Window {
    google?: GoogleClient;
  }
}

export type CurrentUser = {
  email: string;
};

export async function getCurrentUser(): Promise<CurrentUser | null> {
  const response = await fetch("/api/me");
  if (!response.ok) {
    return null;
  }
  return (await response.json()) as CurrentUser;
}

export async function requireAuthenticatedUser(): Promise<CurrentUser> {
  const user = await getCurrentUser();
  if (!user) {
    window.location.href = "/login";
    throw new Error("Not authenticated");
  }
  return user;
}

export async function logout(): Promise<void> {
  await fetch("/api/auth/logout", { method: "POST" });
  window.location.href = "/login";
}

export async function getGoogleClientId(): Promise<string> {
  const appConfigResp = await fetch("/api/config");
  if (!appConfigResp.ok) {
    throw new Error("Unable to load login configuration from backend.");
  }

  const appConfig = (await appConfigResp.json()) as { google_client_id?: string };
  const clientId = appConfig.google_client_id ?? "";
  if (!clientId) {
    throw new Error("Google login is not configured. Set GOOGLE_CLIENT_ID in backend.");
  }
  return clientId;
}

export async function signInWithGoogleCredential(credential: string): Promise<void> {
  const response = await fetch("/api/auth/google", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential }),
  });
  if (!response.ok) {
    const details = await response.text();
    throw new Error(`Login failed: ${details}`);
  }
}
