"use client";

import {
  useEffect,
  useRef,
  useState,
} from "react";

import { useApiClient } from "@/lib/api";
import { WorkspaceSearch } from "./workspace-search";
import { WorkspaceAgent } from "./workspace-agent";


type Workspace = {
  id: string;
  name: string;
  slug: string;
};


type DocumentItem = {
  id: string;
  name: string;
  status: string;
  created_at: string;
  latest_version: {
    id: string;
    version_number: number;
    original_filename: string;
    content_type: string;
    size_bytes: number | null;
    status: string;
    created_at: string;
    uploaded_at: string | null;
  } | null;
};


export function WorkspaceDocuments() {
  const { request } = useApiClient();

  const [workspaces, setWorkspaces] =
    useState<Workspace[]>([]);

  const [
    selectedWorkspaceId,
    setSelectedWorkspaceId,
  ] = useState<string>("");

  const [documents, setDocuments] =
    useState<DocumentItem[]>([]);

  const [workspaceName, setWorkspaceName] =
    useState("");

  const [workspaceSlug, setWorkspaceSlug] =
    useState("");

  const [
    creatingWorkspace,
    setCreatingWorkspace,
  ] = useState(false);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);


  useEffect(() => {
    let cancelled = false;

    async function loadWorkspaces() {
      try {
        setError(null);

        const data =
          await request<Workspace[]>(
            "/api/v1/workspaces",
          );

        if (cancelled) {
          return;
        }

        setWorkspaces(data);

        setSelectedWorkspaceId(
          (current) =>
            current ||
            data[0]?.id ||
            "",
        );
      } catch (err) {
        if (cancelled) {
          return;
        }

        setError(
          err instanceof Error
            ? err.message
            : "Failed to load workspaces",
        );
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadWorkspaces();

    return () => {
      cancelled = true;
    };
  }, [request]);


  useEffect(() => {
    if (!selectedWorkspaceId) {
      return;
    }

    let cancelled = false;

    async function loadDocuments() {
      try {
        const data =
          await request<DocumentItem[]>(
            `/api/v1/workspaces/${selectedWorkspaceId}/documents`,
          );

        if (cancelled) {
          return;
        }

        setDocuments(data);
        setError(null);
      } catch (err) {
        if (cancelled) {
          return;
        }

        setError(
          err instanceof Error
            ? err.message
            : "Failed to load documents",
        );
      }
    }

    void loadDocuments();

    return () => {
      cancelled = true;
    };
  }, [
    request,
    selectedWorkspaceId,
  ]);


  async function createWorkspace() {
    if (
      !workspaceName.trim() ||
      !workspaceSlug.trim()
    ) {
      setError(
        "Workspace name and slug are required.",
      );

      return;
    }

    setCreatingWorkspace(true);
    setError(null);
    setDocuments([]);

    try {
      const workspace =
        await request<Workspace>(
          "/api/v1/workspaces",
          {
            method: "POST",
            body: JSON.stringify({
              name: workspaceName.trim(),
              slug: workspaceSlug.trim(),
            }),
          },
        );

      setWorkspaces((current) => [
        ...current,
        workspace,
      ]);

      setSelectedWorkspaceId(
        workspace.id,
      );

      setWorkspaceName("");
      setWorkspaceSlug("");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to create workspace",
      );
    } finally {
      setCreatingWorkspace(false);
    }
  }


  async function downloadDocument(
    documentId: string,
  ) {
    if (!selectedWorkspaceId) {
      return;
    }

    try {
      setError(null);

      const result =
        await request<{ url: string }>(
          `/api/v1/workspaces/${selectedWorkspaceId}` +
            `/documents/${documentId}/download-url`,
        );

      window.open(
        result.url,
        "_blank",
        "noopener,noreferrer",
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to create download URL",
      );
    }
  }


  async function refreshDocuments(
    workspaceId: string,
  ) {
    try {
      const data =
        await request<DocumentItem[]>(
          `/api/v1/workspaces/${workspaceId}/documents`,
        );

      setDocuments(data);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to refresh documents",
      );
    }
  }


  if (loading) {
    return (
      <div className="rounded-lg border p-6">
        Loading workspaces...
      </div>
    );
  }


  return (
    <section className="mt-10 space-y-8">

      {/* Workspace selector */}
      <div className="rounded-lg border p-6">
        <div className="flex flex-col gap-4">

          <div>
            <h2 className="text-xl font-semibold">
              Workspaces
            </h2>

            <p className="mt-1 text-sm text-gray-500">
              Documents are isolated by workspace.
            </p>
          </div>


          {workspaces.length > 0 ? (
            <select
              value={selectedWorkspaceId}
              onChange={(event) => {
                setDocuments([]);
                setError(null);

                setSelectedWorkspaceId(
                  event.target.value,
                );
              }}
              className="rounded-md border px-3 py-2"
            >
              {workspaces.map(
                (workspace) => (
                  <option
                    key={workspace.id}
                    value={workspace.id}
                  >
                    {workspace.name}
                  </option>
                ),
              )}
            </select>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">

              <input
                value={workspaceName}
                onChange={(event) =>
                  setWorkspaceName(
                    event.target.value,
                  )
                }
                placeholder="Workspace name"
                className="rounded-md border px-3 py-2"
              />


              <input
                value={workspaceSlug}
                onChange={(event) =>
                  setWorkspaceSlug(
                    event.target.value.toLowerCase(),
                  )
                }
                placeholder="workspace-slug"
                className="rounded-md border px-3 py-2"
              />


              <button
                onClick={() =>
                  void createWorkspace()
                }
                disabled={creatingWorkspace}
                className="rounded-md bg-black px-4 py-2 text-sm text-white md:col-span-2 disabled:opacity-50"
              >
                {creatingWorkspace
                  ? "Creating..."
                  : "Create workspace"}
              </button>

            </div>
          )}

        </div>
      </div>


      {/* Semantic search */}
      {selectedWorkspaceId && (
        <WorkspaceSearch
          workspaceId={
            selectedWorkspaceId
          }
        />
      )}


      {/* Agentic copilot */}
      {selectedWorkspaceId && (
        <WorkspaceAgent workspaceId={selectedWorkspaceId} />
      )}

      {/* Document upload */}
      {selectedWorkspaceId && (
        <DocumentUploadSection
          workspaceId={
            selectedWorkspaceId
          }
          onUploadComplete={() =>
            refreshDocuments(
              selectedWorkspaceId,
            )
          }
        />
      )}


      {/* Documents */}
      <div className="rounded-lg border p-6">

        <h2 className="text-xl font-semibold">
          Documents
        </h2>


        {!selectedWorkspaceId ? (
          <p className="mt-4 text-sm text-gray-500">
            Select a workspace to view documents.
          </p>
        ) : documents.length === 0 ? (
          <p className="mt-4 text-sm text-gray-500">
            No documents uploaded yet.
          </p>
        ) : (
          <div className="mt-4 divide-y">

            {documents.map(
              (document) => (
                <div
                  key={document.id}
                  className="flex items-center justify-between gap-4 py-4"
                >

                  <div>
                    <p className="font-medium">
                      {document.name}
                    </p>

                    <p className="text-sm text-gray-500">
                      Status:{" "}
                      {document.status}
                    </p>
                  </div>


                  {document.status ===
                    "uploaded" && (
                    <button
                      onClick={() =>
                        void downloadDocument(
                          document.id,
                        )
                      }
                      className="rounded-md border px-3 py-2 text-sm"
                    >
                      Download
                    </button>
                  )}

                </div>
              ),
            )}

          </div>
        )}

      </div>


      {/* Global error */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

    </section>
  );
}


function DocumentUploadSection({
  workspaceId,
  onUploadComplete,
}: {
  workspaceId: string;
  onUploadComplete: () => void | Promise<void>;
}) {
  const { request } = useApiClient();

  const fileInputRef =
    useRef<HTMLInputElement | null>(
      null,
    );

  const [
    selectedFile,
    setSelectedFile,
  ] = useState<File | null>(null);

  const [
    uploading,
    setUploading,
  ] = useState(false);

  const [
    progress,
    setProgress,
  ] = useState<string>("");

  const [
    uploadError,
    setUploadError,
  ] = useState<string | null>(
    null,
  );


  async function uploadDocument() {
    if (!selectedFile) {
      setUploadError(
        "Choose a document first.",
      );

      return;
    }

    setUploading(true);
    setUploadError(null);
    setProgress(
      "Creating upload intent...",
    );

    try {
      const intent =
        await request<{
          document_id: string;
          version_id: string;
          object_key: string;
          upload_url: string;
          upload_headers: Record<
            string,
            string
          >;
          expires_in_seconds: number;
        }>(
          `/api/v1/workspaces/${workspaceId}` +
            `/documents/upload-intent`,
          {
            method: "POST",
            body: JSON.stringify({
              filename:
                selectedFile.name,
              content_type:
                selectedFile.type ||
                "application/octet-stream",
              size_bytes:
                selectedFile.size,
            }),
          },
        );


      setProgress(
        "Uploading directly to object storage...",
      );


      const uploadResponse =
        await fetch(
          intent.upload_url,
          {
            method: "PUT",
            headers:
              intent.upload_headers,
            body: selectedFile,
          },
        );


      if (!uploadResponse.ok) {
        throw new Error(
          `Object storage upload failed (${uploadResponse.status})`,
        );
      }


      setProgress(
        "Confirming upload...",
      );


      await request(
        `/api/v1/workspaces/${workspaceId}` +
          `/documents/${intent.document_id}` +
          `/versions/${intent.version_id}/complete`,
        {
          method: "POST",
        },
      );


      setProgress(
        "Upload complete.",
      );

      setSelectedFile(null);

      if (fileInputRef.current) {
        fileInputRef.current.value =
          "";
      }

      await onUploadComplete();
    } catch (err) {
      setUploadError(
        err instanceof Error
          ? err.message
          : "Upload failed",
      );

      setProgress("");
    } finally {
      setUploading(false);
    }
  }


  return (
    <div className="rounded-lg border p-6">

      <h2 className="text-xl font-semibold">
        Upload document
      </h2>


      <p className="mt-1 text-sm text-gray-500">
        PDF, DOCX, Markdown, and TXT up to
        25 MB.
      </p>


      <div className="mt-5 space-y-4">

        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.md,.txt"
          onChange={(event) => {
            setSelectedFile(
              event.target.files?.[0] ??
                null,
            );

            setUploadError(null);
            setProgress("");
          }}
          className="block w-full rounded-md border p-2"
        />


        {selectedFile && (
          <div className="text-sm">

            <p className="font-medium">
              {selectedFile.name}
            </p>

            <p className="text-gray-500">
              {(
                selectedFile.size /
                1024 /
                1024
              ).toFixed(2)}{" "}
              MB
            </p>

          </div>
        )}


        <button
          onClick={() =>
            void uploadDocument()
          }
          disabled={
            !selectedFile ||
            uploading
          }
          className="rounded-md bg-black px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          {uploading
            ? "Uploading..."
            : "Upload document"}
        </button>


        {progress && (
          <p className="text-sm text-gray-600">
            {progress}
          </p>
        )}


        {uploadError && (
          <p className="text-sm text-red-600">
            {uploadError}
          </p>
        )}

      </div>
    </div>
  );
}