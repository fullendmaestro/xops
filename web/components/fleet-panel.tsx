"use client"

import { Truck, CheckCircle2, AlertCircle, Loader2 } from "lucide-react"

import { useDrones } from "@/lib/api/requests"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

function formatPos(pos?: { x: number; y: number; z: number }) {
  if (!pos) return "—"
  return `${pos.x.toFixed(1)}, ${pos.y.toFixed(1)}`
}

function DroneStatusBadge({ status }: { status: string }) {
  switch (status) {
    case "idle":
      return (
        <Badge className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-300">
          <CheckCircle2 className="mr-1 size-3" />
          Idle
        </Badge>
      )
    case "busy":
      return (
        <Badge className="bg-sky-500/10 text-sky-700 dark:text-sky-300">
          <Loader2 className="mr-1 size-3 animate-spin" />
          Busy
        </Badge>
      )
    case "error":
      return (
        <Badge className="bg-red-500/10 text-red-700 dark:text-red-300">
          <AlertCircle className="mr-1 size-3" />
          Error
        </Badge>
      )
    default:
      return <Badge variant="outline">{status}</Badge>
  }
}

export function FleetPanel() {
  const { data: drones, isPending, isError } = useDrones()

  return (
    <Card className="border-border/70 shadow-sm xl:col-span-2">
      <CardHeader className="border-b border-border/70 pb-4">
        <CardTitle>Fleet snapshot</CardTitle>
        <CardDescription>
          Real-time drone status from the swarm network.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 p-4">
        {isPending ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3 rounded-xl border bg-background p-3">
              <Skeleton className="size-8 rounded-lg" />
              <div className="flex-1 space-y-1">
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-3 w-36" />
              </div>
              <Skeleton className="h-6 w-14 rounded-full" />
            </div>
          ))
        ) : isError ? (
          <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
            Could not reach swarm. Is the simulation running?
          </div>
        ) : !drones || drones.length === 0 ? (
          <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
            No drones found in fleet.
          </div>
        ) : (
          drones.map((drone) => (
            <div
              key={drone.id}
              className="flex items-center justify-between rounded-xl border bg-background p-3"
            >
              <div className="flex min-w-0 items-center gap-3">
                <div className="rounded-lg bg-muted p-2">
                  <Truck className="size-4" />
                </div>
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">{drone.id}</div>
                  <div className="truncate text-xs text-muted-foreground">
                    Home {formatPos(drone.capabilities?.base_location)} · Rep{" "}
                    {drone.reputation?.toFixed(0) ?? "—"}
                    {drone.current_request && (
                      <> · {drone.current_request.slice(0, 10)}…</>
                    )}
                  </div>
                </div>
              </div>
              <DroneStatusBadge status={drone.status} />
            </div>
          ))
        )}
      </CardContent>
    </Card>
  )
}
