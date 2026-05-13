import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  getCurrentUser,
  requireAuthenticatedUser,
  logout,
  getGoogleClientId,
  signInWithGoogleCredential,
} from "../common";

describe("common.ts", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("returns current user when /api/me succeeds", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ email: "dev@canonical.com" }),
    });

    const user = await getCurrentUser();

    expect(fetchMock).toHaveBeenCalledWith("/api/me");
    expect(user).toEqual({ email: "dev@canonical.com" });
  });

  it("returns null when /api/me fails", async () => {
    fetchMock.mockResolvedValueOnce({ ok: false });

    const user = await getCurrentUser();

    expect(user).toBeNull();
  });

  it("redirects and throws when user is not authenticated", async () => {
    fetchMock.mockResolvedValueOnce({ ok: false });

    await expect(requireAuthenticatedUser()).rejects.toThrow("Not authenticated");
    expect(fetchMock).toHaveBeenCalledWith("/api/me");
  });

  it("posts logout and redirects", async () => {
    fetchMock.mockResolvedValueOnce({ ok: true });

    await logout();

    expect(fetchMock).toHaveBeenCalledWith("/api/auth/logout", { method: "POST" });
  });

  it("loads Google client id from /api/config", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ google_client_id: "client-id-123" }),
    });

    await expect(getGoogleClientId()).resolves.toBe("client-id-123");
  });

  it("throws when Google client id is missing", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    });

    await expect(getGoogleClientId()).rejects.toThrow("Google login is not configured");
  });

  it("throws with details on Google sign-in failure", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      text: async () => "invalid token",
    });

    await expect(signInWithGoogleCredential("abc")).rejects.toThrow("Login failed: invalid token");
  });
});
