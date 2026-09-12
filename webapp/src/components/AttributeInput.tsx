import { useQuery } from "@tanstack/react-query";
import { assetsApi, membersApi, schemasApi } from "../api/client";
import { SchemaAttribute } from "../api/types";
import { AssetPicker } from "./AssetPicker";
import { UserPicker } from "./UserPicker";

function descendantSchemaUids(allSchemas: { uid: string; parent_schema_uid: string | null }[], rootUid: string): Set<string> {
  const children = new Map<string, string[]>();
  for (const s of allSchemas) {
    if (s.parent_schema_uid) {
      children.set(s.parent_schema_uid, [...(children.get(s.parent_schema_uid) ?? []), s.uid]);
    }
  }
  const result = new Set<string>();
  const stack = [rootUid];
  while (stack.length > 0) {
    const current = stack.pop()!;
    for (const child of children.get(current) ?? []) {
      if (!result.has(child)) {
        result.add(child);
        stack.push(child);
      }
    }
  }
  return result;
}

function UserInput({
  value,
  onChange,
  disabled,
}: {
  value: unknown;
  onChange: (value: unknown) => void;
  disabled: boolean;
}) {
  const members = useQuery({ queryKey: ["members"], queryFn: membersApi.directory });
  return (
    <UserPicker
      members={members.data ?? []}
      value={typeof value === "string" ? value : null}
      onChange={onChange}
      disabled={disabled || members.isLoading}
      placeholder={members.isLoading ? "Loading…" : "Search members…"}
    />
  );
}

function CurrentUserInput({ value, base }: { value: unknown; base: string }) {
  const members = useQuery({ queryKey: ["members"], queryFn: membersApi.directory });
  const member = members.data?.find((m) => m.user_id === value);
  const label = value ? member?.name || member?.email || String(value) : "— set automatically —";
  return (
    <input
      className={`${base} bg-slate-100 text-slate-500`}
      disabled
      readOnly
      value={label}
      title="Set automatically to whoever creates or last edits this record"
    />
  );
}

function ReferenceInput({
  attribute,
  value,
  onChange,
  disabled,
  base,
}: {
  attribute: SchemaAttribute;
  value: unknown;
  onChange: (value: unknown) => void;
  disabled: boolean;
  base: string;
}) {
  const allSchemas = useQuery({
    queryKey: ["schemas"],
    queryFn: schemasApi.list,
    enabled: !!attribute.includeChildren,
  });
  const targets = useQuery({
    queryKey: ["assets", attribute.referenceSchemaUid],
    queryFn: () => assetsApi.list(attribute.referenceSchemaUid),
    enabled: !!attribute.referenceSchemaUid && !attribute.includeChildren,
  });
  const allAssets = useQuery({
    queryKey: ["assets"],
    queryFn: () => assetsApi.list(),
    enabled: !!attribute.referenceSchemaUid && !!attribute.includeChildren,
  });

  if (!attribute.referenceSchemaUid) {
    // Legacy attribute with only a display label, no linked schema — fall
    // back to entering the target uid directly.
    return (
      <input
        className={base}
        disabled={disabled}
        placeholder="Asset uid"
        value={typeof value === "string" ? value : ""}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }

  let options = targets.data;
  if (attribute.includeChildren && allAssets.data) {
    const allowed = descendantSchemaUids(allSchemas.data ?? [], attribute.referenceSchemaUid);
    allowed.add(attribute.referenceSchemaUid);
    options = allAssets.data.filter((a) => allowed.has(a.schema_uid));
  }

  const isLoading = attribute.includeChildren
    ? allSchemas.isLoading || allAssets.isLoading
    : targets.isLoading;

  return (
    <AssetPicker
      options={options ?? []}
      value={typeof value === "string" ? value : null}
      onChange={onChange}
      disabled={disabled || isLoading}
      placeholder={isLoading ? "Loading…" : "Search assets…"}
    />
  );
}

function SingleAttributeInput({
  attribute,
  value,
  onChange,
  disabled,
}: {
  attribute: SchemaAttribute;
  value: unknown;
  onChange: (value: unknown) => void;
  disabled: boolean;
}) {
  const base =
    "w-full rounded border border-slate-300 px-2 py-1.5 text-sm disabled:bg-slate-100";

  switch (attribute.type) {
    case "boolean":
      return (
        <input
          type="checkbox"
          checked={Boolean(value)}
          disabled={disabled}
          onChange={(e) => onChange(e.target.checked)}
          className="h-4 w-4"
        />
      );
    case "integer":
    case "float":
      return (
        <input
          type="number"
          step={attribute.type === "float" ? "any" : 1}
          className={base}
          disabled={disabled}
          value={value === undefined || value === null ? "" : String(value)}
          onChange={(e) =>
            onChange(e.target.value === "" ? null : Number(e.target.value))
          }
        />
      );
    case "date":
      return (
        <input
          type="date"
          className={base}
          disabled={disabled}
          value={typeof value === "string" ? value.slice(0, 10) : ""}
          onChange={(e) => onChange(e.target.value)}
        />
      );
    case "datetime":
      return (
        <input
          type="datetime-local"
          className={base}
          disabled={disabled}
          value={typeof value === "string" ? value.slice(0, 16) : ""}
          onChange={(e) => onChange(e.target.value)}
        />
      );
    case "text":
      return (
        <textarea
          className={base}
          rows={3}
          disabled={disabled}
          value={typeof value === "string" ? value : ""}
          onChange={(e) => onChange(e.target.value)}
        />
      );
    case "enumeration":
      return (
        <select
          className={base}
          disabled={disabled}
          value={typeof value === "string" ? value : ""}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">—</option>
          {(attribute.options ?? []).map((opt) => (
            <option key={opt.id} value={opt.value}>
              {opt.value}
            </option>
          ))}
        </select>
      );
    case "reference":
      return (
        <ReferenceInput
          attribute={attribute}
          value={value}
          onChange={onChange}
          disabled={disabled}
          base={base}
        />
      );
    case "user":
      return <UserInput value={value} onChange={onChange} disabled={disabled} />;
    case "current_user":
      return <CurrentUserInput value={value} base={base} />;
    default:
      return (
        <input
          className={base}
          disabled={disabled}
          value={typeof value === "string" ? value : value == null ? "" : String(value)}
          onChange={(e) => onChange(e.target.value)}
        />
      );
  }
}

export function AttributeInput({
  attribute,
  value,
  onChange,
}: {
  attribute: SchemaAttribute;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  const disabled = attribute.readOnly ?? false;

  if (!attribute.multiValue) {
    return (
      <SingleAttributeInput
        attribute={attribute}
        value={value}
        onChange={onChange}
        disabled={disabled}
      />
    );
  }

  const values = Array.isArray(value) ? value : [];
  const atMax =
    attribute.maxCardinality !== undefined && values.length >= attribute.maxCardinality;

  return (
    <div className="space-y-1.5">
      {values.map((v, i) => (
        <div key={i} className="flex items-center gap-1.5">
          <div className="flex-1">
            <SingleAttributeInput
              attribute={attribute}
              value={v}
              onChange={(nv) => {
                const next = [...values];
                next[i] = nv;
                onChange(next);
              }}
              disabled={disabled}
            />
          </div>
          {!disabled && (
            <button
              type="button"
              onClick={() => onChange(values.filter((_, idx) => idx !== i))}
              className="text-xs text-red-500 hover:text-red-700"
            >
              Remove
            </button>
          )}
        </div>
      ))}
      {!disabled && !atMax && (
        <button
          type="button"
          onClick={() => onChange([...values, null])}
          className="text-xs text-slate-600 hover:text-slate-900"
        >
          + Add value
        </button>
      )}
      {(attribute.minCardinality !== undefined || attribute.maxCardinality !== undefined) && (
        <p className="text-[11px] text-slate-400">
          {attribute.minCardinality !== undefined && `min ${attribute.minCardinality}`}
          {attribute.minCardinality !== undefined && attribute.maxCardinality !== undefined && " · "}
          {attribute.maxCardinality !== undefined && `max ${attribute.maxCardinality}`}
        </p>
      )}
    </div>
  );
}
