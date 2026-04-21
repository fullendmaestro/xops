"use client"

import * as React from "react"
import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table"
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronsLeftIcon,
  ChevronsRightIcon,
} from "lucide-react"
import { formatDistanceToNow } from "date-fns"

import type { HistoryEntry } from "@/lib/models/marketplace"
import { useOrderHistory } from "@/lib/api/requests"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

function formatPos(pos?: { x: number; y: number; z: number }) {
  if (!pos) return "—"
  return `${pos.x.toFixed(1)}, ${pos.y.toFixed(1)}`
}

const columns: ColumnDef<HistoryEntry>[] = [
  {
    accessorKey: "request_id",
    header: "Request",
    cell: ({ row }) => (
      <div className="font-mono text-xs text-muted-foreground">
        {row.original.request_id.slice(0, 12)}
      </div>
    ),
  },
  {
    accessorKey: "customer_id",
    header: "Customer",
  },
  {
    id: "route",
    header: "Route",
    cell: ({ row }) => (
      <div className="max-w-56 truncate text-sm text-muted-foreground">
        {formatPos(row.original.pickup)} {"→"} {formatPos(row.original.dropoff)}
      </div>
    ),
  },
  {
    accessorKey: "awarded_drone",
    header: "Drone",
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {row.original.awarded_drone ?? "—"}
      </span>
    ),
  },
  {
    accessorKey: "final_price",
    header: () => <div className="w-full text-right">Price</div>,
    cell: ({ row }) => (
      <div className="text-right tabular-nums">
        {row.original.final_price != null
          ? `$${row.original.final_price.toFixed(2)}`
          : "—"}
      </div>
    ),
  },
  {
    accessorKey: "package_weight",
    header: () => <div className="w-full text-right">Weight</div>,
    cell: ({ row }) => (
      <div className="text-right tabular-nums">
        {row.original.package_weight} kg
      </div>
    ),
  },
  {
    accessorKey: "completed_at",
    header: "Completed",
    cell: ({ row }) =>
      row.original.completed_at ? (
        <span className="text-xs text-muted-foreground">
          {formatDistanceToNow(new Date(row.original.completed_at * 1000), {
            addSuffix: true,
          })}
        </span>
      ) : (
        "—"
      ),
  },
  {
    id: "status",
    header: "Status",
    cell: () => (
      <Badge className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-300">
        Completed
      </Badge>
    ),
  },
]

export function OrderHistoryTable() {
  const [page, setPage] = React.useState(1)
  const limit = 10
  const { data, isPending, isError } = useOrderHistory(page, limit)
  const [sorting, setSorting] = React.useState<SortingState>([
    { id: "completed_at", desc: true },
  ])

  const table = useReactTable({
    data: data?.history ?? [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    manualPagination: true,
    pageCount: data?.total_pages ?? 1,
  })

  if (isPending) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full rounded-lg" />
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <div className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
        Could not load delivery history. Is the simulation running?
      </div>
    )
  }

  return (
    <div className="w-full flex-col gap-4">
      <div className="mb-2 flex items-center justify-between px-1">
        <p className="text-sm text-muted-foreground">
          {data?.total_completed ?? 0} total completed deliveries
        </p>
      </div>

      <div className="overflow-hidden rounded-lg border">
        <Table>
          <TableHeader className="sticky top-0 z-10 bg-muted">
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id}>
                {hg.headers.map((h) => (
                  <TableHead key={h.id} colSpan={h.colSpan}>
                    {h.isPlaceholder
                      ? null
                      : flexRender(h.column.columnDef.header, h.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length > 0 ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center text-muted-foreground"
                >
                  No completed deliveries yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between px-1 pt-4">
        <div className="text-sm text-muted-foreground">
          Page {page} of {data?.total_pages ?? 1}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            className="hidden size-8 lg:flex"
            size="icon"
            onClick={() => setPage(1)}
            disabled={page <= 1}
          >
            <span className="sr-only">First page</span>
            <ChevronsLeftIcon />
          </Button>
          <Button
            variant="outline"
            className="size-8"
            size="icon"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
          >
            <span className="sr-only">Previous page</span>
            <ChevronLeftIcon />
          </Button>
          <Button
            variant="outline"
            className="size-8"
            size="icon"
            onClick={() => setPage((p) => p + 1)}
            disabled={page >= (data?.total_pages ?? 1)}
          >
            <span className="sr-only">Next page</span>
            <ChevronRightIcon />
          </Button>
          <Button
            variant="outline"
            className="hidden size-8 lg:flex"
            size="icon"
            onClick={() => setPage(data?.total_pages ?? 1)}
            disabled={page >= (data?.total_pages ?? 1)}
          >
            <span className="sr-only">Last page</span>
            <ChevronsRightIcon />
          </Button>
        </div>
      </div>
    </div>
  )
}
