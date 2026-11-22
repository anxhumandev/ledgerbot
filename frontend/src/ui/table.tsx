import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Columns3 } from "lucide-react";
import { type ReactNode, useMemo } from "react";
import { num } from "../lib/fmt";
import { cx, Empty, IconButton, Skeleton } from "./core";
import { Menu } from "./overlay";

export type Column<T> = {
  key: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  sortKey?: string;
  align?: "left" | "right" | "center";
  width?: string;
  hideable?: boolean;
  className?: string;
};

export function DataTable<T>({ rows, columns, rowKey, sort, onSort, loading, empty, onRowClick, selected, onSelect, hidden, dense, activeKey }: {
  rows: T[] | undefined; columns: Column<T>[]; rowKey: (r: T) => string; sort?: { key: string; order: "asc" | "desc" };
  onSort?: (key: string) => void; loading?: boolean; empty?: ReactNode; onRowClick?: (r: T) => void;
  selected?: Set<string>; onSelect?: (keys: Set<string>) => void; hidden?: Set<string>; dense?: boolean; activeKey?: string | null;
}) {
  const cols = columns.filter((c) => !hidden?.has(c.key));
  const allKeys = useMemo(() => (rows ?? []).map(rowKey), [rows]);
  const allChecked = !!selected && allKeys.length > 0 && allKeys.every((k) => selected.has(k));
  return (
    <div className="overflow-x-auto scroll-thin">
      <table className="w-full border-collapse text-left text-[13px]">
        <thead>
          <tr className="border-b border-edge bg-panel-2">
            {onSelect && (
              <th className="w-10 px-3 py-2.5">
                <input type="checkbox" aria-label="Select all rows on this page" checked={allChecked}
                  onChange={(e) => onSelect(new Set(e.target.checked ? allKeys : []))} className="h-4 w-4 accent-[var(--brand)]" />
              </th>
            )}
            {cols.map((c) => {
              const active = sort && c.sortKey && sort.key === c.sortKey;
              return (
                <th key={c.key} scope="col" style={{ width: c.width }}
                  aria-sort={active ? (sort!.order === "asc" ? "ascending" : "descending") : undefined}
                  className={cx("whitespace-nowrap px-3 py-2.5 text-[12px] font-semibold text-fg-3", c.align === "right" && "text-right", c.align === "center" && "text-center")}>
                  {c.sortKey && onSort ? (
                    <button onClick={() => onSort(c.sortKey!)} className={cx("inline-flex items-center gap-1 hover:text-fg", active && "text-fg")}>
                      {c.header}
                      {active ? (sort!.order === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} />) : <ArrowDown size={12} className="opacity-25" />}
                    </button>
                  ) : c.header}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {loading && !rows?.length
            ? Array.from({ length: 8 }).map((_, i) => (
              <tr key={i} className="border-b border-edge">
                {onSelect && <td className="px-3 py-3"><Skeleton className="h-4 w-4" /></td>}
                {cols.map((c) => <td key={c.key} className="px-3 py-3"><Skeleton className="h-4 w-full max-w-[160px]" /></td>)}
              </tr>
            ))
            : rows?.map((r) => {
              const k = rowKey(r);
              return (
                <tr key={k} onClick={onRowClick ? () => onRowClick(r) : undefined}
                  onKeyDown={onRowClick ? (e) => { if (e.key === "Enter") onRowClick(r); } : undefined}
                  tabIndex={onRowClick ? 0 : undefined}
                  className={cx("border-b border-edge last:border-0 transition-colors", onRowClick && "cursor-pointer hover:bg-panel-2 focus:bg-brand-soft/50",
                    activeKey === k && "bg-brand-soft/60", loading && "opacity-60")}>
                  {onSelect && (
                    <td className="px-3" onClick={(e) => e.stopPropagation()}>
                      <input type="checkbox" aria-label={`Select ${k}`} checked={selected?.has(k) ?? false} className="h-4 w-4 accent-[var(--brand)]"
                        onChange={(e) => { const s = new Set(selected); e.target.checked ? s.add(k) : s.delete(k); onSelect(s); }} />
                    </td>
                  )}
                  {cols.map((c) => (
                    <td key={c.key} className={cx("px-3 align-middle text-fg-2", dense ? "py-2" : "py-2.5", c.align === "right" && "text-right", c.align === "center" && "text-center", c.className)}>
                      {c.cell(r)}
                    </td>
                  ))}
                </tr>
              );
            })}
        </tbody>
      </table>
      {!loading && rows && rows.length === 0 && (empty ?? <Empty title="No results" body="Nothing matches the current filters." />)}
    </div>
  );
}

export function Pagination({ page, pageSize, total, onPage, onPageSize }: { page: number; pageSize: number; total: number; onPage: (p: number) => void; onPageSize?: (n: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = total ? (page - 1) * pageSize + 1 : 0;
  const to = Math.min(total, page * pageSize);
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-edge px-4 py-2.5 text-[12px] text-fg-3">
      <span className="num">{num(from)}–{num(to)} of {num(total)}</span>
      <div className="flex items-center gap-3">
        {onPageSize && (
          <label className="flex items-center gap-1.5">Rows
            <select value={pageSize} onChange={(e) => onPageSize(Number(e.target.value))} className="h-7 rounded-md border border-edge-strong bg-panel px-1.5 text-[12px] text-fg">
              {[25, 50, 100].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
        )}
        <span className="num">Page {page} of {pages}</span>
        <div className="flex">
          <IconButton label="Previous page" disabled={page <= 1} onClick={() => onPage(page - 1)}><ChevronLeft size={16} /></IconButton>
          <IconButton label="Next page" disabled={page >= pages} onClick={() => onPage(page + 1)}><ChevronRight size={16} /></IconButton>
        </div>
      </div>
    </div>
  );
}

export function ColumnPicker<T>({ columns, hidden, onChange }: { columns: Column<T>[]; hidden: Set<string>; onChange: (h: Set<string>) => void }) {
  return (
    <Menu width={220} trigger={({ toggle, open }) => (
      <button onClick={toggle} aria-expanded={open} className="inline-flex h-9 items-center gap-2 rounded-full border border-edge-strong bg-panel px-3 text-[13px] font-semibold text-fg-2 hover:bg-panel-2">
        <Columns3 size={15} />Columns
      </button>
    )}>
      {() => (
        <div className="p-1">
          {columns.filter((c) => c.hideable).map((c) => (
            <label key={c.key} className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-[13px] text-fg-2 hover:bg-panel-2">
              <input type="checkbox" checked={!hidden.has(c.key)} className="h-4 w-4 accent-[var(--brand)]"
                onChange={(e) => { const h = new Set(hidden); e.target.checked ? h.delete(c.key) : h.add(c.key); onChange(h); }} />
              {c.header}
            </label>
          ))}
        </div>
      )}
    </Menu>
  );
}
