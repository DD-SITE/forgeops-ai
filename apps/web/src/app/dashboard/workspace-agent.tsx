"use client";

import { FormEvent, useState } from "react";
import { useAuth } from "@clerk/nextjs";

import { useApiClient } from "@/lib/api";

type Action = {
  id: string;
  action_type: string;
  status: string;
  payload: Record<string, unknown>;
  result: Record<string, unknown> | null;
};

type Run = {
  id: string;
  status: string;
  answer: string | null;
  error: string | null;
  actions: Action[];
};

type AgentEvent =
  | {
      type: "complete";
      data: Run;
    }
  | {
      type: "error";
      message: string;
    };

export function WorkspaceAgent({
  workspaceId,
}: {
  workspaceId: string;
}) {
  const { request } = useApiClient();
  const { getToken } = useAuth();

  const [query, setQuery] = useState("");
  const [run, setRun] = useState<Run | null>(null);
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState("");

  async function submit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    const trimmedQuery = query.trim();

    if (!trimmedQuery || running) {
      return;
    }

    setRunning(true);
    setMessage("");
    setRun(null);

    try {
      const token = await getToken();

      if (!token) {
        throw new Error(
          "Authentication token is unavailable. Please sign in again.",
        );
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/workspaces/${workspaceId}/agent/runs/stream`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            query: trimmedQuery,
          }),
        },
      );

      if (!response.ok) {
        const body = await response.text();

        throw new Error(
          body ||
            `Agent request failed with status ${response.status}`,
        );
      }

      if (!response.body) {
        throw new Error(
          "Agent response did not contain a readable stream.",
        );
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      let buffer = "";

      while (true) {
        const { value, done } =
          await reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(value, {
          stream: true,
        });

        const frames = buffer.split("\n\n");

        buffer = frames.pop() ?? "";

        for (const frame of frames) {
          processSseFrame(frame);
        }
      }

      buffer += decoder.decode();

      if (buffer.trim()) {
        processSseFrame(buffer);
      }
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Agent failed.",
      );
    } finally {
      setRunning(false);
    }
  }

  function processSseFrame(frame: string) {
    const lines = frame
      .split(/\r?\n/)
      .filter(Boolean);

    const eventLine = lines.find((line) =>
      line.startsWith("event:"),
    );

    const dataLine = lines.find((line) =>
      line.startsWith("data:"),
    );

    if (!dataLine) {
      return;
    }

    const eventName =
      eventLine?.slice("event:".length).trim() ??
      "message";

    const rawData = dataLine
      .slice("data:".length)
      .trim();

    if (!rawData) {
      return;
    }

    let data: unknown;

    try {
      data = JSON.parse(rawData);
    } catch {
      setMessage(
        "Received an invalid response from the agent.",
      );

      return;
    }

    if (eventName === "complete") {
      setRun(data as Run);
      return;
    }

    if (eventName === "error") {
      const errorData =
        data as Partial<{
          message: string;
        }>;

      setMessage(
        errorData.message ??
          "Agent failed.",
      );

      return;
    }
  }

  async function decide(
    decision: "approve" | "reject",
  ) {
    if (!run || running) {
      return;
    }

    setRunning(true);
    setMessage("");

    try {
      const updated =
        await request<Run>(
          `/api/v1/workspaces/${workspaceId}/agent/runs/${run.id}/approval`,
          {
            method: "POST",
            body: JSON.stringify({
              decision,
            }),
          },
        );

      setRun(updated);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Approval failed.",
      );
    } finally {
      setRunning(false);
    }
  }

  const proposedAction =
    run?.actions.find(
      (action) =>
        action.status === "proposed",
    );

  return (
    <section className="rounded-lg border p-6">
      <div>
        <h2 className="text-xl font-semibold">
          Engineering Copilot
        </h2>

        <p className="mt-1 text-sm text-gray-500">
          Investigate incidents, search engineering
          knowledge, and propose guarded actions.
        </p>
      </div>

      <form
        onSubmit={submit}
        className="mt-5 space-y-3"
      >
        <textarea
          value={query}
          onChange={(event) =>
            setQuery(event.target.value)
          }
          placeholder="Why did the payment service start returning 5xx errors after the latest deployment?"
          rows={4}
          disabled={running}
          className="w-full rounded-md border px-3 py-2 outline-none focus:ring-2"
        />

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={
              running ||
              !query.trim()
            }
            className="rounded-md bg-black px-5 py-2 text-sm text-white disabled:opacity-50"
          >
            {running
              ? "Investigating..."
              : "Run copilot"}
          </button>

          {running && (
            <span className="text-sm text-gray-500">
              Agent is working...
            </span>
          )}
        </div>
      </form>

      {message && (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {message}
        </div>
      )}

      {run && (
        <div className="mt-6 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">
              Run status
            </span>

            <span className="rounded-full bg-gray-100 px-3 py-1 text-xs">
              {run.status}
            </span>
          </div>

          {run.answer && (
            <article className="rounded-lg border p-4">
              <h3 className="font-medium">
                Answer
              </h3>

              <p className="mt-3 whitespace-pre-wrap text-sm leading-6">
                {run.answer}
              </p>
            </article>
          )}

          {run.actions.length > 0 && (
            <article className="rounded-lg border p-4">
              <h3 className="font-medium">
                Agent actions
              </h3>

              <div className="mt-4 space-y-3">
                {run.actions.map(
                  (action) => (
                    <div
                      key={action.id}
                      className="rounded-md border p-3"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-mono text-xs">
                          {action.action_type}
                        </span>

                        <span className="rounded-full bg-gray-100 px-2 py-1 text-xs">
                          {action.status}
                        </span>
                      </div>

                      <pre className="mt-3 overflow-auto rounded bg-gray-50 p-3 text-xs">
                        {JSON.stringify(
                          action.payload,
                          null,
                          2,
                        )}
                      </pre>

                      {action.result && (
                        <pre className="mt-3 overflow-auto rounded bg-gray-50 p-3 text-xs">
                          {JSON.stringify(
                            action.result,
                            null,
                            2,
                          )}
                        </pre>
                      )}
                    </div>
                  ),
                )}
              </div>
            </article>
          )}

          {proposedAction && (
            <article className="rounded-lg border border-amber-300 bg-amber-50 p-4">
              <h3 className="font-medium">
                Approval required
              </h3>

              <p className="mt-1 text-sm text-amber-800">
                The agent has proposed an action
                that requires your approval before
                execution.
              </p>

              <pre className="mt-3 overflow-auto rounded bg-white p-3 text-xs">
                {JSON.stringify(
                  proposedAction.payload,
                  null,
                  2,
                )}
              </pre>

              <div className="mt-4 flex gap-3">
                <button
                  type="button"
                  disabled={running}
                  onClick={() =>
                    void decide("approve")
                  }
                  className="rounded-md bg-black px-4 py-2 text-sm text-white disabled:opacity-50"
                >
                  Approve
                </button>

                <button
                  type="button"
                  disabled={running}
                  onClick={() =>
                    void decide("reject")
                  }
                  className="rounded-md border px-4 py-2 text-sm disabled:opacity-50"
                >
                  Reject
                </button>
              </div>
            </article>
          )}

          {run.error && (
            <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              {run.error}
            </div>
          )}
        </div>
      )}
    </section>
  );
}