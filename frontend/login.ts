import { getGoogleClientId, signInWithGoogleCredential } from "./common";

function setError(message: string): void {
  const status = document.getElementById("error");
  if (!status) {
    return;
  }
  status.textContent = message;
  status.classList.remove("u-hide");
}

async function bootstrap(): Promise<void> {
  const container = document.getElementById("google-signin");
  if (!container) {
    return;
  }

  const configResp = await fetch("/api/health");
  if (!configResp.ok) {
    setError("Backend not reachable.");
    return;
  }

  let clientId = "";
  try {
    clientId = await getGoogleClientId();
  } catch (error: unknown) {
    setError(error instanceof Error ? error.message : "Failed to load login configuration.");
    return;
  }

  // Wait for Google Sign-In script to load (it's loaded with async defer)
  const waitForGoogle = async (maxAttempts = 50): Promise<boolean> => {
    for (let i = 0; i < maxAttempts; i++) {
      if (window.google?.accounts?.id) {
        return true;
      }
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    return false;
  };

  const googleLoaded = await waitForGoogle();
  if (!googleLoaded) {
    setError("Google Sign-In script did not load. Please check your internet connection or try disabling ad blockers.");
    return;
  }

  window.google.accounts.id.initialize({
    client_id: clientId,
    callback: async (resp) => {
      try {
        await signInWithGoogleCredential(resp.credential);
        window.location.href = "/index.html";
      } catch (error: unknown) {
        setError(error instanceof Error ? error.message : "Login failed.");
      }
    },
  });

  window.google.accounts.id.renderButton(container, {
    theme: "outline",
    size: "large",
    shape: "rectangular",
  });
}

void bootstrap();