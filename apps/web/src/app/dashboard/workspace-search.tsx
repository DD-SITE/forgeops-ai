"use client";

import { FormEvent, useState } from "react";

import { useApiClient } from "@/lib/api";

type SearchResult = {
  chunk_id: string;
  document_id: string;
  document_name: string;
  content: string;
  similarity: number;
  page_start: number | null;
  page_end: number | null;
  section_path: string[] | null;
};

export function WorkspaceSearch({
  workspaceId,
}: {
  workspaceId: string;
}) {
  const { request } = useApiClient();

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<
    SearchResult[]
  >([]);

  const [searching, setSearching] =
    useState(false);

  const [error, setError] = useState<
    string | null
  >(null);

  async function handleSearch(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!query.trim()) {
      return;
    }

    setSearching(true);
    setError(null);

    try {
      const response = await request<{
        query: string;
        results: SearchResult[];
      }>(
        `/api/v1/workspaces/${workspaceId}/search`,
        {
          method: "POST",
          body: JSON.stringify({
            query,
            top_k: 5,
            min_similarity: 0.15,
          }),
        },
      );

      setResults(response.results);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Search failed",
      );

      setResults([]);
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="rounded-lg border p-6">
      <h2 className="text-xl font-semibold">
        Search workspace knowledge
      </h2>

      <p className="mt-1 text-sm text-gray-500">
        Semantic search across uploaded documents.
      </p>

      <form
        onSubmit={handleSearch}
        className="mt-5 flex gap-3"
      >
        <input
          value={query}
          onChange={(event) =>
            setQuery(event.target.value)
          }
          placeholder="Ask about your documents..."
          className="flex-1 rounded-md border px-3 py-2"
        />

        <button
          type="submit"
          disabled={
            searching || !query.trim()
          }
          className="rounded-md bg-black px-5 py-2 text-sm text-white disabled:opacity-50"
        >
          {searching
            ? "Searching..."
            : "Search"}
        </button>
      </form>

      {error && (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {results.length > 0 && (
        <div className="mt-6 space-y-4">
          {results.map((result) => (
            <article
              key={result.chunk_id}
              className="rounded-lg border p-4"
            >
              <div className="flex items-center justify-between gap-4">
                <h3 className="font-medium">
                  {result.document_name}
                </h3>

                <span className="rounded-full bg-gray-100 px-2 py-1 text-xs">
                  {(result.similarity * 100).toFixed(
                    1,
                  )}
                  % match
                </span>
              </div>

              {result.section_path && (
                <p className="mt-2 text-xs text-gray-500">
                  {result.section_path.join(" / ")}
                </p>
              )}

              <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-gray-700">
                {result.content}
              </p>

              {(result.page_start ||
                result.page_end) && (
                <p className="mt-3 text-xs text-gray-500">
                  Pages{" "}
                  {result.page_start}
                  {result.page_end &&
                  result.page_end !==
                    result.page_start
                    ? `–${result.page_end}`
                    : ""}
                </p>
              )}
            </article>
          ))}
        </div>
      )}

      {!searching &&
        !error &&
        query &&
        results.length === 0 && (
          <p className="mt-6 text-sm text-gray-500">
            No sufficiently similar results found.
          </p>
        )}
    </div>
  );
}