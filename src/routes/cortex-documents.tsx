/* eslint-disable i18next/no-literal-string -- Cortex admin surface is English-only until translations land; Canvas UI stays localized. */
import { useState, type FormEvent } from "react";
import { describeCortexError } from "#/api/cortex/cortex-api";
import {
  useCreateDocument,
  useDeleteDocument,
  useDocuments,
  useSearchDocuments,
} from "#/api/cortex/cortex-hooks";
import { useCortexWorkspace } from "#/components/features/cortex/cortex-workspace";
import {
  CortexButton,
  CortexCard,
  CortexInput,
  CortexLabel,
  CortexState,
  CortexTextarea,
} from "#/components/features/cortex/cortex-ui";

export default function CortexDocuments() {
  const { activeOrgId, role } = useCortexWorkspace();
  const documents = useDocuments(activeOrgId);
  const createDocument = useCreateDocument(activeOrgId);
  const deleteDocument = useDeleteDocument(activeOrgId);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const search = useSearchDocuments(activeOrgId, searchQuery);
  const canDelete = role === "owner" || role === "admin";

  const submit = (event: FormEvent) => {
    event.preventDefault();
    createDocument.mutate(
      { title, content },
      {
        onSuccess: () => {
          setTitle("");
          setContent("");
        },
      },
    );
  };

  if (!activeOrgId) {
    return (
      <p className="text-sm text-tertiary-light">{"No organization yet"}</p>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <CortexCard title={"New document"}>
        <form className="space-y-3" onSubmit={submit}>
          <label className="block">
            <CortexLabel>{"Title"}</CortexLabel>
            <CortexInput
              required
              maxLength={300}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </label>
          <label className="block">
            <CortexLabel>{"Content"}</CortexLabel>
            <CortexTextarea
              rows={6}
              required
              value={content}
              onChange={(event) => setContent(event.target.value)}
            />
          </label>
          <CortexButton type="submit" disabled={createDocument.isPending}>
            {"Add document"}
          </CortexButton>
          {createDocument.error && (
            <p className="text-sm text-danger">
              {describeCortexError(createDocument.error)}
            </p>
          )}
        </form>
      </CortexCard>

      <CortexCard title={"Documents"}>
        <CortexState
          isLoading={documents.isLoading}
          error={documents.error}
          isEmpty={documents.data?.length === 0}
          emptyLabel={"No documents yet"}
        >
          <ul className="divide-y divide-border text-sm">
            {documents.data?.map((document) => (
              <li
                key={document.id}
                className="flex flex-wrap items-center justify-between gap-2 py-2"
              >
                <span>
                  <span className="text-content">{document.title}</span>
                  <span className="ml-2 text-xs text-tertiary-light">
                    {document.status} · {document.size_bytes ?? 0} B
                  </span>
                </span>
                {canDelete && (
                  <CortexButton
                    variant="danger"
                    onClick={() => deleteDocument.mutate(document.id)}
                  >
                    {"Delete"}
                  </CortexButton>
                )}
              </li>
            ))}
          </ul>
        </CortexState>
      </CortexCard>

      <CortexCard title={"Search"}>
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            setSearchQuery(searchInput);
          }}
        >
          <CortexInput
            className="min-w-56 flex-1"
            placeholder={"Search your documents"}
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
          />
          <CortexButton type="submit">{"Search"}</CortexButton>
        </form>
        {searchQuery.length > 1 && (
          <div className="mt-3">
            <CortexState
              isLoading={search.isLoading}
              error={search.error}
              isEmpty={search.data?.hits.length === 0}
              emptyLabel={"No documents yet"}
            >
              <ul className="space-y-2">
                {search.data?.hits.map((hit) => (
                  <li
                    key={`${hit.document_id}-${hit.chunk_index}`}
                    className="rounded-lg bg-surface-raised p-2 text-sm"
                  >
                    <p className="text-xs text-tertiary-light">
                      {hit.document_title} · {"chunk"} {hit.chunk_index}
                    </p>
                    <p className="whitespace-pre-wrap">{hit.content}</p>
                  </li>
                ))}
              </ul>
            </CortexState>
          </div>
        )}
      </CortexCard>
    </div>
  );
}
