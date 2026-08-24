"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback } from "react";

export function useApiClient() {
  const { getToken } = useAuth();

  const request = useCallback(
    async <T>(
      path: string,
      options: RequestInit = {},
    ): Promise<T> => {
      const token = await getToken();

      const headers = new Headers(options.headers);

      if (!(options.body instanceof FormData)) {
        headers.set("Content-Type", "application/json");
      }

      if (token) {
        headers.set("Authorization", `Bearer ${token}`);
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}${path}`,
        {
          ...options,
          headers,
        },
      );

      if (!response.ok) {
        const body = await response.text();

        throw new Error(
          body || `Request failed with status ${response.status}`,
        );
      }

      return response.json() as Promise<T>;
    },
    [getToken],
  );

  return { request };
}