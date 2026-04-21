"use client"

import { useState } from "react"
import {
  ChevronRight,
  Plus,
  Search,
} from "lucide-react"

import { useRequests, useDrones } from "@/lib/api/requests"
import { AppSidebar } from "@/components/app-sidebar"
import { CreateOrderDialog } from "@/components/create-order-dialog"
import { FleetPanel } from "@/components/fleet-panel"
import { MarketplaceStats } from "@/components/marketplace-stats"
import { OrderHistoryTable } from "@/components/order-history-table"
import { OrderTable } from "@/components/order-table"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TooltipProvider } from "@/components/ui/tooltip"

export default function Home() {
  const [activeTab, setActiveTab] = useState("orders")
  const [isCreateOrderOpen, setIsCreateOrderOpen] = useState(false)

  const { data: requests = [] } = useRequests()
  const { data: drones = [] } = useDrones()

  const tabLabel: Record<string, string> = {
    orders: "Orders",
    overview: "Overview",
    history: "History",
    fleet: "Fleet",
    signals: "Signals",
  }

  return (
    <TooltipProvider>
      <SidebarProvider>
        <AppSidebar
          activeTab={activeTab}
          onTabChange={setActiveTab}
          orderCount={requests.length}
        />

        <SidebarInset className="bg-[radial-gradient(circle_at_top_left,rgba(0,0,0,0.04),transparent_28%),linear-gradient(to_bottom,rgba(255,255,255,0.85),rgba(255,255,255,1))] dark:bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.05),transparent_28%),linear-gradient(to_bottom,rgba(2,6,23,0.98),rgba(2,6,23,1))]">
          <Tabs
            value={activeTab}
            onValueChange={setActiveTab}
            className="flex min-h-screen flex-col"
          >
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
                          <span className="text-foreground">
                            {tabLabel[activeTab] ?? activeTab}
                          </span>
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
                    <TabsTrigger value="history">History</TabsTrigger>
                    <TabsTrigger value="fleet">Fleet</TabsTrigger>
                    <TabsTrigger value="signals">Signals</TabsTrigger>
                  </TabsList>
                </div>
              </header>

              <main className="flex-1 px-4 py-6 md:px-6 lg:px-8">
                {/* ── Orders ── */}
                <TabsContent value="orders" className="mt-0">
                  <OrderTable requests={requests} />
                </TabsContent>

                {/* ── Overview ── */}
                <TabsContent value="overview" className="mt-0 space-y-6">
                  <MarketplaceStats />

                  <section className="grid gap-6 xl:grid-cols-5">
                    <Card className="border-border/70 shadow-sm xl:col-span-3">
                      <CardHeader className="border-b border-border/70 pb-4">
                        <CardTitle>Dispatch overview</CardTitle>
                        <CardDescription>
                          Request activity across the swarm.
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
                            ),
                          )}
                        </div>

                        <div className="grid gap-3 md:grid-cols-3">
                          <div className="rounded-xl border bg-background p-3">
                            <div className="text-xs text-muted-foreground">
                              Queue health
                            </div>
                            <div className="mt-1 text-lg font-semibold">
                              {requests.length > 0 ? "Active" : "Empty"}
                            </div>
                          </div>
                          <div className="rounded-xl border bg-background p-3">
                            <div className="text-xs text-muted-foreground">
                              Drone fleet
                            </div>
                            <div className="mt-1 text-lg font-semibold">
                              {drones.filter((d) => d.status === "idle").length}{" "}
                              / {drones.length} ready
                            </div>
                          </div>
                          <div className="rounded-xl border bg-background p-3">
                            <div className="text-xs text-muted-foreground">
                              Assigned
                            </div>
                            <div className="mt-1 text-lg font-semibold">
                              {requests.filter((r) => r.assigned_drone).length}{" "}
                              active
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>

                    <FleetPanel />
                  </section>
                </TabsContent>

                {/* ── History ── */}
                <TabsContent value="history" className="mt-0">
                  <Card className="border-border/70 shadow-sm">
                    <CardHeader className="border-b border-border/70 pb-4">
                      <CardTitle>Delivery history</CardTitle>
                      <CardDescription>
                        All completed deliveries, newest first.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="p-4">
                      <OrderHistoryTable />
                    </CardContent>
                  </Card>
                </TabsContent>

                {/* ── Fleet ── */}
                <TabsContent value="fleet" className="mt-0">
                  <Card className="border-border/70 shadow-sm">
                    <CardHeader className="border-b border-border/70 pb-4">
                      <CardTitle>Fleet workspace</CardTitle>
                      <CardDescription>
                        Detailed view of all drones in the swarm.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="grid gap-4 p-4 md:grid-cols-2 xl:grid-cols-4">
                      {drones.length === 0 ? (
                        <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground md:col-span-2 xl:col-span-4">
                          No drones available. Is the simulation running?
                        </div>
                      ) : (
                        drones.map((drone) => (
                          <div
                            key={drone.id}
                            className="rounded-xl border bg-background p-4 space-y-2"
                          >
                            <div className="flex items-center justify-between">
                              <div className="font-medium">{drone.id}</div>
                              <span
                                className={
                                  drone.status === "idle"
                                    ? "text-xs text-emerald-600 dark:text-emerald-400"
                                    : "text-xs text-sky-600 dark:text-sky-400"
                                }
                              >
                                {drone.status}
                              </span>
                            </div>
                            <div className="text-xs text-muted-foreground space-y-1">
                              <div>
                                Payload: {drone.capabilities?.max_payload ?? "—"} kg
                              </div>
                              <div>
                                Range: {drone.capabilities?.max_range ?? "—"} m
                              </div>
                              <div>
                                Reputation: {drone.reputation?.toFixed(1) ?? "—"}
                              </div>
                              {drone.current_request && (
                                <div className="truncate">
                                  Job: {drone.current_request}
                                </div>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </CardContent>
                  </Card>
                </TabsContent>

                {/* ── Signals ── */}
                <TabsContent value="signals" className="mt-0">
                  <Card className="border-border/70 shadow-sm">
                    <CardHeader className="border-b border-border/70 pb-4">
                      <CardTitle>Signal center</CardTitle>
                      <CardDescription>
                        Tashi consensus network health.
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
                        <div className="text-sm font-medium">Active peers</div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          {drones.length + 2} nodes in swarm
                        </div>
                      </div>
                      <div className="rounded-xl border bg-background p-4">
                        <div className="text-sm font-medium">Alerts</div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          No critical events
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>
              </main>
            </div>
          </Tabs>

          <CreateOrderDialog
            open={isCreateOrderOpen}
            onOpenChange={setIsCreateOrderOpen}
          />
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  )
}
