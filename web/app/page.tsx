"use client"

import { useEffect, useMemo, useState, type ComponentType } from "react"
import {
  AlertCircle,
  ChevronRight,
  CircleDot,
  ClipboardList,
  Plus,
  Search,
  ShieldCheck,
  Truck,
} from "lucide-react"

import type {
  DeliveryRequest,
  Drone,
  LocationOption,
} from "@/lib/models/dashboard"
import { AppSidebar } from "@/components/app-sidebar"
import { OrderTable } from "@/components/order-table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Field, FieldGroup } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TooltipProvider } from "@/components/ui/tooltip"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000"

type RawRequest = {
  request_id?: string
  customer_id?: string
  status?: string
  pickup_location?: string
  dropoff_location?: string
  pickup?: { x: number; y: number; z: number }
  dropoff?: { x: number; y: number; z: number }
  package_weight?: number
  assigned_drone?: string | null
  awarded_drone?: string | null
}

type RawDrone = {
  id?: string
  capabilities?: {
    base_location?: { x: number; y: number; z: number }
  }
}

const formatPosition = (position?: { x: number; y: number; z: number }) => {
  if (!position) return "Unknown"
  return `${position.x.toFixed(1)}, ${position.y.toFixed(1)}, ${position.z.toFixed(1)}`
}

const normalizeRequests = (payload: unknown): DeliveryRequest[] => {
  if (Array.isArray(payload)) {
    return payload as DeliveryRequest[]
  }

  if (!payload || typeof payload !== "object") {
    return []
  }

  const activeRequests = (
    payload as { active_requests?: Record<string, RawRequest> }
  ).active_requests
  if (!activeRequests || typeof activeRequests !== "object") {
    return []
  }

  return Object.entries(activeRequests).map(([requestId, request]) => ({
    request_id: request.request_id ?? requestId,
    customer_id: request.customer_id ?? "unknown",
    status: request.status ?? "pending",
    pickup_location: request.pickup_location ?? formatPosition(request.pickup),
    dropoff_location:
      request.dropoff_location ?? formatPosition(request.dropoff),
    package_weight: Number(request.package_weight ?? 0),
    assigned_drone: request.assigned_drone ?? request.awarded_drone ?? null,
  }))
}

const normalizeDrones = (payload: unknown): Drone[] => {
  if (Array.isArray(payload)) {
    return payload as Drone[]
  }

  if (!payload || typeof payload !== "object") {
    return []
  }

  return Object.entries(payload as Record<string, RawDrone>).map(
    ([key, drone]) => ({
      id: drone.id ?? key,
      name: drone.id ?? key,
      status: "available",
      battery_level: 100,
      location: drone.capabilities?.base_location ?? { x: 0, y: 0, z: 0 },
    })
  )
}

function StatCard({
  title,
  value,
  description,
  icon: Icon,
}: {
  title: string
  value: string
  description: string
  icon: ComponentType<{ className?: string }>
}) {
  return (
    <Card className="border-border/70 shadow-sm">
      <CardContent className="flex items-start justify-between gap-4 p-4">
        <div className="space-y-1">
          <div className="text-sm text-muted-foreground">{title}</div>
          <div className="text-2xl font-semibold tracking-tight">{value}</div>
          <div className="text-sm text-muted-foreground">{description}</div>
        </div>
        <div className="rounded-xl border bg-muted/50 p-2 text-foreground/80">
          <Icon className="size-4" />
        </div>
      </CardContent>
    </Card>
  )
}

export default function Home() {
  const [pickupOptions, setPickupOptions] = useState<LocationOption[]>([])
  const [dropoffOptions, setDropoffOptions] = useState<LocationOption[]>([])
  const [requests, setRequests] = useState<DeliveryRequest[]>([])
  const [drones, setDrones] = useState<Drone[]>([])
  const [isCreateOrderOpen, setIsCreateOrderOpen] = useState(false)

  const [customerId, setCustomerId] = useState("cust_001")
  const [pickupId, setPickupId] = useState("")
  const [dropoffId, setDropoffId] = useState("")
  const [weight, setWeight] = useState("1.0")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    const fetchLocations = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/locations`)
        if (!res.ok) {
          return
        }

        const data = await res.json()
        setPickupOptions(data.pickup || [])
        setDropoffOptions(data.dropoff || [])
      } catch (err) {
        console.error("Failed to fetch locations:", err)
      }
    }

    const fetchData = async () => {
      try {
        const [reqRes, droneRes] = await Promise.all([
          fetch(`${API_BASE_URL}/api/requests`),
          fetch(`${API_BASE_URL}/api/drones`),
        ])

        if (reqRes.ok) {
          const data = await reqRes.json()
          setRequests(normalizeRequests(data))
        }

        if (droneRes.ok) {
          const data = await droneRes.json()
          setDrones(normalizeDrones(data))
        }
      } catch (err) {
        console.error("Failed to fetch data:", err)
      }
    }

    fetchLocations()
    const interval = setInterval(fetchData, 30000)
    fetchData()

    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (!pickupId && pickupOptions.length > 0) {
      setPickupId(pickupOptions[0].id)
    }
  }, [pickupId, pickupOptions])

  useEffect(() => {
    if (!dropoffId && dropoffOptions.length > 0) {
      setDropoffId(dropoffOptions[0].id)
    }
  }, [dropoffId, dropoffOptions])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)
    setError("")

    try {
      const res = await fetch(`${API_BASE_URL}/api/requests`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_id: customerId,
          pickup: pickupId,
          dropoff: dropoffId,
          package_weight: parseFloat(weight),
        }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setError(data.error || "Request failed")
        return
      }

      setWeight("1.0")
      setIsCreateOrderOpen(false)

      const reqRes = await fetch(`${API_BASE_URL}/api/requests`)
      if (reqRes.ok) {
        const data = await reqRes.json()
        setRequests(normalizeRequests(data))
      }
    } catch (err) {
      setError("Network error")
      console.error(err)
    } finally {
      setIsSubmitting(false)
    }
  }

  const summary = useMemo(() => {
    const totalRequests = requests.length
    const pendingRequests = requests.filter(
      (request) =>
        !["delivered", "returning"].includes(request.status.toLowerCase())
    ).length
    const assignedRequests = requests.filter(
      (request) => request.assigned_drone
    ).length
    const availableDrones = drones.filter(
      (drone) => drone.status === "available"
    ).length

    return {
      totalRequests,
      pendingRequests,
      assignedRequests,
      availableDrones,
    }
  }, [drones, requests])

  return (
    <TooltipProvider>
      <SidebarProvider>
        <AppSidebar />

        <SidebarInset className="bg-[radial-gradient(circle_at_top_left,rgba(0,0,0,0.04),transparent_28%),linear-gradient(to_bottom,rgba(255,255,255,0.85),rgba(255,255,255,1))] dark:bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.05),transparent_28%),linear-gradient(to_bottom,rgba(2,6,23,0.98),rgba(2,6,23,1))]">
          <Tabs defaultValue="orders" className="flex min-h-screen flex-col">
            <div className="flex flex-col">
              <header className="border-b bg-background/80 backdrop-blur">
                <div className="flex flex-col gap-4 px-4 py-4 md:px-6 lg:px-8">
                  <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <div className="flex items-center gap-3">
                      <SidebarTrigger />
                      <Separator
                        orientation="vertical"
                        className="hidden h-6 md:block"
                      />
                      <div>
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <span>Dashboard</span>
                          <ChevronRight className="size-3" />
                          <span className="text-foreground">Orders</span>
                        </div>
                        <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">
                          XOPS Marketplace
                        </h1>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <div className="hidden items-center gap-2 rounded-lg border bg-background px-3 py-2 text-sm text-muted-foreground md:flex">
                        <Search className="size-4" />
                        <span>Search orders, drones, or bids</span>
                      </div>
                      <Button onClick={() => setIsCreateOrderOpen(true)}>
                        <Plus className="size-4" />
                        Create order
                      </Button>
                    </div>
                  </div>

                  <TabsList variant="line" className="w-full justify-start">
                    <TabsTrigger value="orders">Orders</TabsTrigger>
                    <TabsTrigger value="overview">Overview</TabsTrigger>
                    <TabsTrigger value="fleet">Fleet</TabsTrigger>
                    <TabsTrigger value="signals">Signals</TabsTrigger>
                  </TabsList>
                </div>
              </header>

              <main className="flex-1 px-4 py-6 md:px-6 lg:px-8">
                <TabsContent value="orders" className="mt-0">
                  <OrderTable requests={requests} />
                </TabsContent>

                <TabsContent value="overview" className="mt-0 space-y-6">
                  <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <StatCard
                      title="Active orders"
                      value={String(summary.totalRequests).padStart(2, "0")}
                      description="All current marketplace requests"
                      icon={ClipboardList}
                    />
                    <StatCard
                      title="Pending awards"
                      value={String(summary.pendingRequests).padStart(2, "0")}
                      description="Requests waiting for assignment"
                      icon={CircleDot}
                    />
                    <StatCard
                      title="Assigned drones"
                      value={String(summary.assignedRequests).padStart(2, "0")}
                      description="Requests with an active carrier"
                      icon={Truck}
                    />
                    <StatCard
                      title="Available fleet"
                      value={String(summary.availableDrones).padStart(2, "0")}
                      description="Ready drones in the swarm"
                      icon={ShieldCheck}
                    />
                  </section>

                  <section className="grid gap-6 xl:grid-cols-5">
                    <Card className="border-border/70 shadow-sm xl:col-span-3">
                      <CardHeader className="border-b border-border/70 pb-4">
                        <CardTitle>Dispatch overview</CardTitle>
                        <CardDescription>
                          Placeholder chart and trend space for the shadcn-style
                          dashboard.
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-4 p-4">
                        <div className="grid grid-cols-12 gap-2 rounded-2xl border bg-muted/30 p-4">
                          {[32, 58, 46, 77, 63, 88, 41, 69, 54, 83, 48, 72].map(
                            (height, index) => (
                              <div
                                key={index}
                                className="flex flex-col items-center gap-2"
                              >
                                <div
                                  className="w-full rounded-t-xl bg-foreground/90"
                                  style={{
                                    height: `${height}%`,
                                    minHeight: "2.25rem",
                                  }}
                                />
                                <div className="text-[11px] text-muted-foreground">
                                  {index + 1}
                                </div>
                              </div>
                            )
                          )}
                        </div>

                        <div className="grid gap-3 md:grid-cols-3">
                          <div className="rounded-xl border bg-background p-3">
                            <div className="text-xs text-muted-foreground">
                              Queue health
                            </div>
                            <div className="mt-1 text-lg font-semibold">
                              Stable
                            </div>
                          </div>
                          <div className="rounded-xl border bg-background p-3">
                            <div className="text-xs text-muted-foreground">
                              Average ETA
                            </div>
                            <div className="mt-1 text-lg font-semibold">
                              12.4 min
                            </div>
                          </div>
                          <div className="rounded-xl border bg-background p-3">
                            <div className="text-xs text-muted-foreground">
                              Bid spread
                            </div>
                            <div className="mt-1 text-lg font-semibold">
                              1.8x
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>

                    <Card className="border-border/70 shadow-sm xl:col-span-2">
                      <CardHeader className="border-b border-border/70 pb-4">
                        <CardTitle>Fleet snapshot</CardTitle>
                        <CardDescription>
                          Static sidebar-style list for the current swarm.
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-3 p-4">
                        {drones.length === 0 ? (
                          <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                            No drones available.
                          </div>
                        ) : (
                          drones.slice(0, 4).map((drone) => (
                            <div
                              key={drone.id}
                              className="flex items-center justify-between rounded-xl border bg-background p-3"
                            >
                              <div className="flex min-w-0 items-center gap-3">
                                <div className="rounded-lg bg-muted p-2">
                                  <Truck className="size-4" />
                                </div>
                                <div className="min-w-0">
                                  <div className="truncate text-sm font-medium">
                                    {drone.name}
                                  </div>
                                  <div className="truncate text-xs text-muted-foreground">
                                    Battery {drone.battery_level}% ·{" "}
                                    {formatPosition(drone.location)}
                                  </div>
                                </div>
                              </div>
                              <Badge variant="outline">Ready</Badge>
                            </div>
                          ))
                        )}
                      </CardContent>
                    </Card>
                  </section>
                </TabsContent>

                <TabsContent value="fleet" className="mt-0">
                  <Card className="border-border/70 shadow-sm">
                    <CardHeader className="border-b border-border/70 pb-4">
                      <CardTitle>Fleet workspace</CardTitle>
                      <CardDescription>
                        Placeholder section for drone cards and maintenance
                        views.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="grid gap-4 p-4 md:grid-cols-2 xl:grid-cols-3">
                      {drones.length === 0 ? (
                        <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground md:col-span-2 xl:col-span-3">
                          No drones available.
                        </div>
                      ) : (
                        drones.map((drone) => (
                          <div
                            key={drone.id}
                            className="rounded-xl border bg-background p-4"
                          >
                            <div className="flex items-center justify-between">
                              <div className="font-medium">{drone.name}</div>
                              <Badge variant="outline">Ready</Badge>
                            </div>
                            <div className="mt-2 text-xs text-muted-foreground">
                              Location {formatPosition(drone.location)}
                            </div>
                          </div>
                        ))
                      )}
                    </CardContent>
                  </Card>
                </TabsContent>

                <TabsContent value="signals" className="mt-0">
                  <Card className="border-border/70 shadow-sm">
                    <CardHeader className="border-b border-border/70 pb-4">
                      <CardTitle>Signal center</CardTitle>
                      <CardDescription>
                        Placeholder tabs, alerts, and telemetry sections.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="grid gap-4 p-4 md:grid-cols-3">
                      <div className="rounded-xl border bg-background p-4">
                        <div className="text-sm font-medium">Consensus</div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          Finality window healthy
                        </div>
                      </div>
                      <div className="rounded-xl border bg-background p-4">
                        <div className="text-sm font-medium">Latency</div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          Network hop times within target
                        </div>
                      </div>
                      <div className="rounded-xl border bg-background p-4">
                        <div className="text-sm font-medium">Alerts</div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          No critical events in the queue
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>
              </main>
            </div>
          </Tabs>

          <Dialog open={isCreateOrderOpen} onOpenChange={setIsCreateOrderOpen}>
            <DialogContent className="sm:max-w-xl">
              <form onSubmit={handleSubmit}>
                <DialogHeader>
                  <DialogTitle>Create order</DialogTitle>
                  <DialogDescription>
                    Where should the drone pick up and deliver?
                  </DialogDescription>
                </DialogHeader>

                <FieldGroup className="mt-4">
                  <Field>
                    <Label htmlFor="customer-id">Customer ID</Label>
                    <Input
                      id="customer-id"
                      value={customerId}
                      onChange={(event) => setCustomerId(event.target.value)}
                      placeholder="cust_001"
                    />
                  </Field>

                  <FieldGroup className="grid grid-cols-2">
                    <Field>
                      <Label htmlFor="pickup-location">Pickup location</Label>
                      <Select value={pickupId} onValueChange={setPickupId}>
                        <SelectTrigger id="pickup-location" className="w-full">
                          <SelectValue placeholder="Select pickup" />
                        </SelectTrigger>
                        <SelectContent>
                          {pickupOptions.map((option) => (
                            <SelectItem key={option.id} value={option.id}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </Field>

                    <Field>
                      <Label htmlFor="dropoff-location">Dropoff location</Label>
                      <Select value={dropoffId} onValueChange={setDropoffId}>
                        <SelectTrigger id="dropoff-location" className="w-full">
                          <SelectValue placeholder="Select dropoff" />
                        </SelectTrigger>
                        <SelectContent>
                          {dropoffOptions.map((option) => (
                            <SelectItem key={option.id} value={option.id}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </Field>
                  </FieldGroup>

                  <Field>
                    <Label htmlFor="package-weight">Package weight (kg)</Label>
                    <Input
                      id="package-weight"
                      type="number"
                      step="0.1"
                      min="0.1"
                      value={weight}
                      onChange={(event) => setWeight(event.target.value)}
                      placeholder="1.0"
                    />
                  </Field>
                </FieldGroup>

                {error && (
                  <div className="mt-4 flex gap-2 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                    <AlertCircle className="size-4 shrink-0" />
                    <span>{error}</span>
                  </div>
                )}

                <DialogFooter className="mt-4">
                  <DialogClose asChild>
                    <Button variant="outline">Cancel</Button>
                  </DialogClose>
                  <Button type="submit" disabled={isSubmitting}>
                    {isSubmitting ? "Creating..." : "Create order"}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  )
}
