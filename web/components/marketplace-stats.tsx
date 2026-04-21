"use client"

import { ClipboardList, CircleDot, Truck, ShieldCheck } from "lucide-react"
import type { ComponentType } from "react"

import { useRequests, useDrones } from "@/lib/api/requests"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

function StatCard({
  title,
  value,
  description,
  icon: Icon,
  loading,
}: {
  title: string
  value: string
  description: string
  icon: ComponentType<{ className?: string }>
  loading?: boolean
}) {
  return (
    <Card className="border-border/70 shadow-sm">
      <CardContent className="flex items-start justify-between gap-4 p-4">
        <div className="space-y-1">
          <div className="text-sm text-muted-foreground">{title}</div>
          {loading ? (
            <Skeleton className="h-8 w-12" />
          ) : (
            <div className="text-2xl font-semibold tracking-tight">{value}</div>
          )}
          <div className="text-sm text-muted-foreground">{description}</div>
        </div>
        <div className="rounded-xl border bg-muted/50 p-2 text-foreground/80">
          <Icon className="size-4" />
        </div>
      </CardContent>
    </Card>
  )
}

export function MarketplaceStats() {
  const { data: requests, isPending: requestsPending } = useRequests()
  const { data: drones, isPending: dronesPending } = useDrones()

  const totalRequests = requests?.length ?? 0
  const pendingRequests =
    requests?.filter(
      (r) => !["delivered", "returning", "completed"].includes(r.status.toLowerCase()),
    ).length ?? 0
  const assignedRequests =
    requests?.filter((r) => r.assigned_drone).length ?? 0
  const availableDrones =
    drones?.filter((d) => d.status === "idle").length ?? 0

  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <StatCard
        title="Active orders"
        value={String(totalRequests).padStart(2, "0")}
        description="All current marketplace requests"
        icon={ClipboardList}
        loading={requestsPending}
      />
      <StatCard
        title="Pending awards"
        value={String(pendingRequests).padStart(2, "0")}
        description="Requests waiting for assignment"
        icon={CircleDot}
        loading={requestsPending}
      />
      <StatCard
        title="Assigned drones"
        value={String(assignedRequests).padStart(2, "0")}
        description="Requests with an active carrier"
        icon={Truck}
        loading={requestsPending}
      />
      <StatCard
        title="Available fleet"
        value={String(availableDrones).padStart(2, "0")}
        description="Ready drones in the swarm"
        icon={ShieldCheck}
        loading={dronesPending}
      />
    </section>
  )
}
