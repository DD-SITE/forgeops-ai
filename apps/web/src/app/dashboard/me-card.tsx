"use client";

import { useCallback, useEffect, useState } from "react";

import { useApiClient } from "@/lib/api";

type CurrentUser = {
  id: string;
  clerk_id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
};

export function MeCard() {
  const { request } = useApiClient();

  const [user, setUser] = useState<CurrentUser | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadUser = useCallback(async () => {
    try {
      setError(null);

      const data = await request<CurrentUser>("/api/v1/me");

      setUser(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load user",
      );
    }
  }, [request]);

  useEffect(() => {
    void loadUser();
  }, [loadUser]);

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6">
        <h2 className="font-semibold text-red-700">
          Failed to load ForgeOps user
        </h2>

        <p className="mt-2 text-sm text-red-600">
          {error}
        </p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="rounded-lg border p-6">
        <p className="text-sm text-gray-500">
          Loading your ForgeOps identity...
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border p-6">
      <h2 className="text-lg font-semibold">
        ForgeOps User
      </h2>

      <dl className="mt-5 space-y-4 text-sm">
        <div>
          <dt className="text-gray-500">
            Database ID
          </dt>

          <dd className="mt-1 break-all font-mono text-xs">
            {user.id}
          </dd>
        </div>

        <div>
          <dt className="text-gray-500">
            Clerk ID
          </dt>

          <dd className="mt-1 break-all font-mono text-xs">
            {user.clerk_id}
          </dd>
        </div>

        <div>
          <dt className="text-gray-500">
            Email
          </dt>

          <dd className="mt-1">
            {user.email}
          </dd>
        </div>

        <div>
          <dt className="text-gray-500">
            Name
          </dt>

          <dd className="mt-1">
            {user.full_name ?? "Not provided"}
          </dd>
        </div>

        <div>
          <dt className="text-gray-500">
            Status
          </dt>

          <dd className="mt-1">
            {user.is_active ? "Active" : "Inactive"}
          </dd>
        </div>
      </dl>
    </div>
  );
}