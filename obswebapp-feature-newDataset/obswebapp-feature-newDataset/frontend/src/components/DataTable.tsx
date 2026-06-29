import { useEffect, useState } from "react";

interface Props {
  columns: string[];
  rows: Record<string, any>[];
  onRowClick?: (row: Record<string, any>, index: number) => void;
  emptyText?: string;
  pageSize?: number;
  truncateColumns?: string[];
}

function fmtCell(v: any): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "number") {
    if (Number.isInteger(v)) return v.toLocaleString();
    return Math.abs(v) < 1
      ? v.toString()
      : v.toLocaleString(undefined, { maximumFractionDigits: 4 });
  }
  return String(v);
}

export default function DataTable({
  columns,
  rows,
  onRowClick,
  emptyText = "No data",
  pageSize,
  truncateColumns,
}: Props) {
  const truncateSet = new Set(truncateColumns ?? []);
  const [page, setPage] = useState(0);

  useEffect(() => {
    setPage(0);
  }, [rows]);

  const total = rows.length;
  // const paged = pageSize
  //   ? rows.slice(page * pageSize, (page + 1) * pageSize)
  //   : rows;

  const [sortOrder, setSortOrder] = useState("desc");

  const sortedRows = [...rows].sort((a, b) =>
    sortOrder === "asc" ? a.cost - b.cost : b.cost - a.cost,
  );

  const paged = pageSize
    ? sortedRows.slice(page * pageSize, (page + 1) * pageSize)
    : sortedRows;

  const hasPrev = page > 0;
  const hasNext = pageSize ? (page + 1) * pageSize < total : false;

  const handleCostSort = () => {
    setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
  };

  return (
    <div>
      <div className="table-wrap">
        <table className="dataframe">
          <thead>
            {/* <tr>
              {columns.map((c) => <th key={c}>{c}</th>)}
            </tr> */}
            <tr>
              {columns.map((c) => (
                <th key={c}>
                  {c}
                  {c === "cost" && (
                    <button
                      onClick={handleCostSort}
                      style={{
                        marginLeft: "6px",
                        border: "none",
                        background: "transparent",
                        cursor: "pointer",
                      }}
                    >
                      {sortOrder === "asc" ? "↑" : "↓"}
                    </button>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paged.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  style={{
                    textAlign: "center",
                    padding: "16px",
                    color: "#6b7280",
                  }}
                >
                  {emptyText}
                </td>
              </tr>
            ) : (
              paged.map((row, i) => {
                const absIdx = pageSize ? page * pageSize + i : i;
                return (
                  <tr
                    key={absIdx}
                    className={onRowClick ? "clickable" : undefined}
                    onClick={
                      onRowClick ? () => onRowClick(row, absIdx) : undefined
                    }
                  >
                    {columns.map((c) => (
                      <td
                        key={c}
                        style={
                          truncateSet.has(c)
                            ? {
                                maxWidth: 280,
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                              }
                            : undefined
                        }
                      >
                        {fmtCell(row[c])}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      {pageSize && total > 0 && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            gap: 8,
            marginTop: 8,
          }}
        >
          <span style={{ fontSize: 11, color: "#9ca3af" }}>
            {page * pageSize + 1}–{Math.min((page + 1) * pageSize, total)} of{" "}
            {total.toLocaleString()}
          </span>
          <button
            className="btn-secondary"
            style={{ padding: "4px 10px", fontSize: 11 }}
            disabled={!hasPrev}
            onClick={() => setPage((p) => p - 1)}
          >
            ← Prev
          </button>
          <button
            className="btn-secondary"
            style={{ padding: "4px 10px", fontSize: 11 }}
            disabled={!hasNext}
            onClick={() => setPage((p) => p + 1)}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
