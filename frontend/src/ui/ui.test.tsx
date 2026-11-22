import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ErrorState, Notice, StatusBadge } from "./core";
import { ConfirmDialog } from "./overlay";
import { DataTable, Pagination } from "./table";

afterEach(cleanup);

const rows = [{ id: "TS-1", name: "Alpha", n: 3 }, { id: "TS-2", name: "Beta", n: 1 }];
const cols = [
  { key: "name", header: "Name", sortKey: "name", cell: (r: any) => r.name },
  { key: "n", header: "Suppliers", sortKey: "n", cell: (r: any) => r.n },
];

describe("DataTable", () => {
  it("renders rows and asks the parent to sort", () => {
    const onSort = vi.fn();
    render(<DataTable rows={rows} columns={cols} rowKey={(r) => r.id} sort={{ key: "name", order: "asc" }} onSort={onSort} />);
    expect(screen.getByText("Alpha")).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: /Name/ }).getAttribute("aria-sort")).toBe("ascending");
    fireEvent.click(screen.getByRole("button", { name: /Suppliers/ }));
    expect(onSort).toHaveBeenCalledWith("n");
  });
  it("shows an empty state", () => {
    render(<DataTable rows={[]} columns={cols} rowKey={(r: any) => r.id} />);
    expect(screen.getByText("No results")).toBeTruthy();
  });
  it("selects all rows on the page", () => {
    const onSelect = vi.fn();
    render(<DataTable rows={rows} columns={cols} rowKey={(r) => r.id} selected={new Set()} onSelect={onSelect} />);
    fireEvent.click(screen.getByLabelText("Select all rows on this page"));
    expect([...onSelect.mock.calls[0][0]]).toEqual(["TS-1", "TS-2"]);
  });
});

describe("Pagination", () => {
  it("disables previous on the first page and moves forward", () => {
    const onPage = vi.fn();
    render(<Pagination page={1} pageSize={25} total={60} onPage={onPage} />);
    expect((screen.getByLabelText("Previous page") as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText("Next page"));
    expect(onPage).toHaveBeenCalledWith(2);
    expect(screen.getByText("1–25 of 60")).toBeTruthy();
  });
});

describe("states", () => {
  it("labels statuses in text, not colour alone", () => {
    render(<StatusBadge status="needs_review" />);
    expect(screen.getByText("Needs review")).toBeTruthy();
  });
  it("shows API error messages with the request id and retries", () => {
    const retry = vi.fn();
    render(<ErrorState error={{ code: "conflict", message: "Case changed", requestId: "req_9" }} onRetry={retry} />);
    expect(screen.getByRole("alert").textContent).toContain("Case changed");
    expect(screen.getByText("Request req_9")).toBeTruthy();
    fireEvent.click(screen.getByText("Retry"));
    expect(retry).toHaveBeenCalled();
  });
  it("renders notices", () => {
    render(<Notice tone="sim">Simulated numbers</Notice>);
    expect(screen.getByText("Simulated numbers")).toBeTruthy();
  });
});

describe("ConfirmDialog", () => {
  it("requires a reason when asked and passes it on", () => {
    const onConfirm = vi.fn();
    render(<ConfirmDialog open onClose={() => {}} onConfirm={onConfirm} title="Reject this match?" confirmLabel="Reject match" reason="Why?" reasonRequired />);
    fireEvent.click(screen.getByText("Reject match"));
    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toContain("Give a short reason");
    fireEvent.change(screen.getByLabelText("Why?"), { target: { value: "different street" } });
    fireEvent.click(screen.getByText("Reject match"));
    expect(onConfirm).toHaveBeenCalledWith("different street");
  });
});
