import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import {
  Control,
  useFieldArray,
  useForm,
  UseFormRegister,
  UseFormSetValue,
  useWatch,
} from "react-hook-form";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { schemasApi, workspacesApi } from "../../api/client";
import { getActiveProfile } from "../../api/session";
import { AppSchema, ATTRIBUTE_TYPES, SchemaAttribute, SchemaInput } from "../../api/types";
import { SchemaPicker } from "../../components/SchemaPicker";

const BUILT_IN_FIELDS: Record<"objects" | "tickets" | "documents", string> = {
  objects: "Every object already has: Name, Key, Type, and creation/update timestamps — no need to redefine them here.",
  tickets: "Every ticket already has: Title, Description, State, Priority, Assignee, Due date, and creation timestamps — no need to redefine them here.",
  documents: "Every document already has: Code, Title, Owner, Responsible service, Authority level, Confidentiality, Source, and its full revision history — no need to redefine them here.",
};

function AttributeRow({
  control,
  register,
  setValue,
  index,
  onRemove,
  watched,
  allSchemas,
  currentWorkspaceId,
}: {
  control: Control<SchemaInput>;
  register: UseFormRegister<SchemaInput>;
  setValue: UseFormSetValue<SchemaInput>;
  index: number;
  onRemove: () => void;
  watched: SchemaAttribute | undefined;
  allSchemas: AppSchema[];
  currentWorkspaceId: string | null | undefined;
}) {
  const {
    fields: optionFields,
    append: appendOption,
    remove: removeOption,
  } = useFieldArray({ control, name: `attributes.${index}.options` as const });

  return (
    <div className="space-y-2 rounded border border-slate-200 p-2">
      <div className="flex items-center gap-2">
        <input
          {...register(`attributes.${index}.name` as const, { required: true })}
          placeholder="Name"
          className="w-1/3 rounded border border-slate-300 px-2 py-1 text-sm"
        />
        <select
          {...register(`attributes.${index}.type` as const)}
          className="rounded border border-slate-300 px-2 py-1 text-sm"
        >
          {ATTRIBUTE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-1 text-xs text-slate-500">
          <input type="checkbox" {...register(`attributes.${index}.required` as const)} />
          required
        </label>
        <label className="flex items-center gap-1 text-xs text-slate-500">
          <input type="checkbox" {...register(`attributes.${index}.unique` as const)} />
          unique
        </label>
        <label className="flex items-center gap-1 text-xs text-slate-500">
          <input type="checkbox" {...register(`attributes.${index}.multiValue` as const)} />
          multi-value
        </label>
        <button
          type="button"
          onClick={onRemove}
          className="ml-auto text-xs text-red-500 hover:text-red-700"
        >
          Remove
        </button>
      </div>

      {watched?.multiValue && (
        <div className="flex items-center gap-2 pl-1 text-xs text-slate-500">
          <label className="flex items-center gap-1">
            Min values
            <input
              type="number"
              min={0}
              {...register(`attributes.${index}.minCardinality` as const, {
                valueAsNumber: true,
              })}
              className="w-16 rounded border border-slate-300 px-2 py-1"
            />
          </label>
          <label className="flex items-center gap-1">
            Max values
            <input
              type="number"
              min={0}
              {...register(`attributes.${index}.maxCardinality` as const, {
                valueAsNumber: true,
              })}
              className="w-16 rounded border border-slate-300 px-2 py-1"
            />
          </label>
        </div>
      )}

      {(watched?.type === "string" || watched?.type === "text") && (
        <div className="flex items-center gap-2 pl-1">
          <label className="text-xs text-slate-500">Regex pattern</label>
          <input
            {...register(`attributes.${index}.regex` as const)}
            placeholder="e.g. ^[A-Z]{3}-\\d+$"
            className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
          />
        </div>
      )}

      {watched?.type === "enumeration" && (
        <div className="space-y-1 pl-1">
          <div className="flex items-center justify-between">
            <label className="text-xs text-slate-500">Choices</label>
            <button
              type="button"
              onClick={() => appendOption({ id: crypto.randomUUID(), value: "" })}
              className="text-xs text-slate-600 hover:text-slate-900"
            >
              + Add choice
            </button>
          </div>
          <div className="space-y-1">
            {optionFields.map((opt, oi) => (
              <div key={opt.id} className="flex items-center gap-1.5">
                <input
                  {...register(`attributes.${index}.options.${oi}.value` as const, {
                    required: true,
                  })}
                  placeholder="Choice value"
                  className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
                />
                <button
                  type="button"
                  onClick={() => removeOption(oi)}
                  className="text-xs text-red-500 hover:text-red-700"
                >
                  Remove
                </button>
              </div>
            ))}
            {optionFields.length === 0 && (
              <p className="text-xs text-slate-400">No choices yet — any value will be accepted.</p>
            )}
          </div>
        </div>
      )}

      {watched?.type === "reference" && (
        <div className="flex items-center gap-2 pl-1">
          <label className="shrink-0 text-xs text-slate-500">References</label>
          <SchemaPicker
            schemas={allSchemas}
            value={watched.referenceSchemaUid}
            currentWorkspaceId={currentWorkspaceId}
            onChange={(uid, schema) => {
              setValue(`attributes.${index}.referenceSchemaUid`, uid);
              setValue(`attributes.${index}.referenceType`, schema?.name ?? "");
            }}
          />
          <label className="flex shrink-0 items-center gap-1 text-xs text-slate-500">
            <input type="checkbox" {...register(`attributes.${index}.includeChildren` as const)} />
            include subtypes
          </label>
        </div>
      )}
    </div>
  );
}

export function SchemaForm() {
  const { uid } = useParams<{ uid: string }>();
  const [searchParams] = useSearchParams();
  const isEditing = !!uid;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const appliesToParam = searchParams.get("applies_to");
  const defaultAppliesTo =
    appliesToParam === "tickets" || appliesToParam === "documents" ? appliesToParam : "objects";

  const profile = getActiveProfile();
  const me = useQuery({ queryKey: ["me"], queryFn: workspacesApi.me });
  const currentWorkspaceId =
    profile?.authType === "oidc" ? profile.activeWorkspaceId : me.data?.workspace_id;

  const existing = useQuery({
    queryKey: ["schemas", uid],
    queryFn: () => schemasApi.get(uid!),
    enabled: isEditing,
  });
  const allSchemas = useQuery({ queryKey: ["schemas"], queryFn: schemasApi.list });

  const { register, control, handleSubmit, reset, setValue } = useForm<SchemaInput>({
    defaultValues: {
      name: "",
      description: "",
      is_concrete: true,
      attributes: [],
      is_global: false,
      applies_to: defaultAppliesTo,
    },
  });
  const { fields, append, remove } = useFieldArray({ control, name: "attributes" });
  const watchedAttributes = useWatch({ control, name: "attributes" });
  const watchedAppliesTo = useWatch({ control, name: "applies_to" }) ?? defaultAppliesTo;
  const watchedParentUid = useWatch({ control, name: "parent_schema_uid" });

  useEffect(() => {
    if (existing.data) {
      reset({
        name: existing.data.name,
        description: existing.data.description ?? "",
        is_concrete: existing.data.is_concrete,
        parent_schema_uid: existing.data.parent_schema_uid ?? undefined,
        attributes: existing.data.attributes,
        is_global: existing.data.is_global,
        applies_to: existing.data.applies_to,
      });
    }
  }, [existing.data, reset]);

  // Candidates for "parent type": same applies_to, and — when editing —
  // never itself or one of its own descendants (that would create a cycle).
  const excludedUids = useMemo(() => {
    if (!uid || !allSchemas.data) return new Set<string>();
    const childrenOf = new Map<string, string[]>();
    for (const s of allSchemas.data) {
      if (s.parent_schema_uid) {
        childrenOf.set(s.parent_schema_uid, [...(childrenOf.get(s.parent_schema_uid) ?? []), s.uid]);
      }
    }
    const excluded = new Set<string>([uid]);
    const stack = [uid];
    while (stack.length > 0) {
      const current = stack.pop()!;
      for (const child of childrenOf.get(current) ?? []) {
        if (!excluded.has(child)) {
          excluded.add(child);
          stack.push(child);
        }
      }
    }
    return excluded;
  }, [uid, allSchemas.data]);

  const parentCandidates = useMemo(
    () =>
      (allSchemas.data ?? []).filter(
        (s) => s.applies_to === watchedAppliesTo && !excludedUids.has(s.uid),
      ),
    [allSchemas.data, watchedAppliesTo, excludedUids],
  );

  const saveMutation = useMutation({
    mutationFn: async (input: SchemaInput) => {
      if (isEditing) return schemasApi.update(uid!, input);
      return schemasApi.create({
        ...input,
        uid: crypto.randomUUID(),
      });
    },
    onSuccess: (schema) => {
      queryClient.invalidateQueries({ queryKey: ["schemas"] });
      navigate(`/schemas/${schema!.uid}`);
    },
  });

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-semibold text-slate-900">
        {isEditing ? "Edit schema" : "New schema"}
      </h1>

      <form
        onSubmit={handleSubmit((values) => saveMutation.mutate(values))}
        className="mt-6 space-y-5"
      >
        <div>
          <label className="block text-sm font-medium text-slate-700">Name</label>
          <input
            {...register("name", { required: true })}
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Description</label>
          <textarea
            {...register("description")}
            rows={2}
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Applies to</label>
          <select
            {...register("applies_to", {
              onChange: () => setValue("parent_schema_uid", undefined),
            })}
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="objects">Object type</option>
            <option value="tickets">Ticket type</option>
            <option value="documents">Document type</option>
          </select>
          <p className="mt-1.5 rounded bg-slate-50 px-2.5 py-1.5 text-xs text-slate-500">
            {BUILT_IN_FIELDS[watchedAppliesTo]}
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Parent type</label>
          <SchemaPicker
            schemas={parentCandidates}
            value={watchedParentUid}
            currentWorkspaceId={currentWorkspaceId}
            placeholder="None — this is a root type"
            onChange={(schemaUid) => setValue("parent_schema_uid", schemaUid || undefined)}
          />
          <p className="mt-1.5 text-xs text-slate-500">
            Leave empty to create a root type. Choosing a parent makes this a subtype — it
            automatically inherits the parent's attributes (and its ancestors'), on top of
            whatever you define below.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <input type="checkbox" {...register("is_concrete")} id="is_concrete" />
          <label htmlFor="is_concrete" className="text-sm text-slate-700">
            Concrete (assets can be created directly from this schema)
          </label>
        </div>

        <div className="flex items-center gap-2">
          <input type="checkbox" {...register("is_global")} id="is_global" />
          <label htmlFor="is_global" className="text-sm text-slate-700">
            Global (visible, and its objects referenceable, from every workspace)
          </label>
        </div>

        <div>
          <div className="flex items-center justify-between">
            <label className="block text-sm font-medium text-slate-700">Attributes</label>
            <button
              type="button"
              onClick={() =>
                append({ id: crypto.randomUUID(), name: "", type: "string", required: false })
              }
              className="text-sm text-slate-600 hover:text-slate-900"
            >
              + Add attribute
            </button>
          </div>

          <div className="mt-2 space-y-2">
            {fields.map((field, index) => (
              <AttributeRow
                key={field.id}
                control={control}
                register={register}
                setValue={setValue}
                index={index}
                onRemove={() => remove(index)}
                watched={watchedAttributes?.[index]}
                allSchemas={allSchemas.data ?? []}
                currentWorkspaceId={currentWorkspaceId}
              />
            ))}
            {fields.length === 0 && (
              <p className="text-sm text-slate-400">No attributes yet.</p>
            )}
          </div>
        </div>

        <button
          type="submit"
          disabled={saveMutation.isPending}
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {saveMutation.isPending ? "Saving…" : "Save schema"}
        </button>
      </form>
    </div>
  );
}
