"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { AlertCircle, CheckCircle, Clock, Truck } from "lucide-react"

// API configuration - connects directly to Tashi Server
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000"

interface LocationOption {
  id: string
  label: string
  position: { x: number; y: number; z: number }
}

interface Drone {
  id: string
  name: string
  status: string
  battery_level: number
  location: { x: number; y: number; z: number }
}

interface DeliveryRequest {
  request_id: string
  customer_id: string
  status: string
  pickup_location: string
  dropoff_location: string
  package_weight: number
  assigned_drone: string | null
}

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

export default function Home() {
  const [pickupOptions, setPickupOptions] = useState<LocationOption[]>([])
  const [dropoffOptions, setDropoffOptions] = useState<LocationOption[]>([])
  const [requests, setRequests] = useState<DeliveryRequest[]>([])
  const [drones, setDrones] = useState<Drone[]>([])

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
        if (res.ok) {
          const data = await res.json()
          setPickupOptions(data.pickup || [])
          setDropoffOptions(data.dropoff || [])
          if (data.pickup?.length > 0) setPickupId(data.pickup[0].id)
          if (data.dropoff?.length > 0) setDropoffId(data.dropoff[0].id)
        }
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
        const data = await res.json()
        setError(data.error || "Request failed")
        return
      }

      // Reset form
      setWeight("1.0")
      const newCustId = `cust_${String(parseInt(customerId.split("_")[1]) + 1).padStart(3, "0")}`
      setCustomerId(newCustId)

      // Refresh requests
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

  const getStatusBadge = (status: string) => {
    const normalizedStatus = status.toLowerCase()

    switch (normalizedStatus) {
      case "DELIVERED":
      case "delivered":
        return (
          <Badge className="bg-green-100 text-green-900 dark:bg-green-900 dark:text-green-100">
            Delivered
          </Badge>
        )
      case "ASSIGNED":
      case "assigned":
      case "NAVIGATING_PICKUP":
      case "navigating_pickup":
      case "AT_PICKUP":
      case "at_pickup":
      case "CARRYING":
      case "carrying":
      case "NAVIGATING_DROPOFF":
      case "navigating_dropoff":
      case "awarded":
        return (
          <Badge className="bg-blue-100 text-blue-900 dark:bg-blue-900 dark:text-blue-100">
            In Progress
          </Badge>
        )
      case "RETURNING":
      case "returning":
        return (
          <Badge className="bg-purple-100 text-purple-900 dark:bg-purple-900 dark:text-purple-100">
            Returning
          </Badge>
        )
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  const totalRequests = requests.length
  const pendingRequests = requests.filter(
    (r) => !["delivered", "returning"].includes(r.status.toLowerCase())
  ).length
  const awardedRequests = requests.filter((r) => r.assigned_drone).length

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-7xl px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold tracking-tight">XOPS</h1>
          <p className="mt-2 text-muted-foreground">
            Decentralized drone delivery marketplace
          </p>
        </div>

        {/* Main Grid */}
        <div className="grid gap-8 lg:grid-cols-3">
          {/* Left Column - Form */}
          <div className="lg:col-span-1">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">New Delivery</CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="customer" className="text-sm">
                      Customer ID
                    </Label>
                    <Input
                      id="customer"
                      value={customerId}
                      onChange={(e) => setCustomerId(e.target.value)}
                      className="h-8 text-sm"
                      placeholder="cust_001"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="pickup" className="text-sm">
                      Pickup Location
                    </Label>
                    <Select value={pickupId} onValueChange={setPickupId}>
                      <SelectTrigger id="pickup" className="h-8 text-sm">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {pickupOptions.map((opt) => (
                          <SelectItem key={opt.id} value={opt.id}>
                            {opt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="dropoff" className="text-sm">
                      Dropoff Location
                    </Label>
                    <Select value={dropoffId} onValueChange={setDropoffId}>
                      <SelectTrigger id="dropoff" className="h-8 text-sm">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {dropoffOptions.map((opt) => (
                          <SelectItem key={opt.id} value={opt.id}>
                            {opt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="weight" className="text-sm">
                      Package Weight (kg)
                    </Label>
                    <Input
                      id="weight"
                      type="number"
                      step="0.1"
                      min="0.1"
                      value={weight}
                      onChange={(e) => setWeight(e.target.value)}
                      className="h-8 text-sm"
                      placeholder="1.0"
                    />
                  </div>

                  {error && (
                    <div className="flex gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
                      <AlertCircle className="size-4 shrink-0" />
                      <span>{error}</span>
                    </div>
                  )}

                  <Button
                    type="submit"
                    disabled={isSubmitting}
                    className="w-full"
                    size="sm"
                  >
                    {isSubmitting ? "Submitting..." : "Submit Request"}
                  </Button>
                </form>
              </CardContent>
            </Card>

            {/* Marketplace Stats */}
            <div className="mt-6 grid gap-3">
              <div className="rounded-lg border border-foreground/10 p-3">
                <div className="text-2xl font-bold">{totalRequests}</div>
                <div className="text-xs text-muted-foreground">
                  Total Requests
                </div>
              </div>
              <div className="rounded-lg border border-foreground/10 p-3">
                <div className="text-2xl font-bold">{pendingRequests}</div>
                <div className="text-xs text-muted-foreground">Pending</div>
              </div>
              <div className="rounded-lg border border-foreground/10 p-3">
                <div className="text-2xl font-bold">{awardedRequests}</div>
                <div className="text-xs text-muted-foreground">Assigned</div>
              </div>
            </div>
          </div>

          {/* Right Column - Status and Fleet */}
          <div className="space-y-6 lg:col-span-2">
            {/* Drone Fleet */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">Drone Fleet</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {drones.length === 0 ? (
                    <div className="text-sm text-muted-foreground">
                      No drones available
                    </div>
                  ) : (
                    drones.map((drone) => (
                      <div
                        key={drone.id}
                        className="flex items-center justify-between rounded-lg border border-foreground/10 p-3"
                      >
                        <div className="flex items-center gap-3">
                          <div className="rounded-full bg-primary/10 p-2">
                            <Truck className="size-4" />
                          </div>
                          <div>
                            <div className="text-sm font-medium">
                              {drone.name}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {drone.status} · {drone.battery_level}% battery
                            </div>
                          </div>
                        </div>
                        <Badge variant="outline" className="text-xs">
                          Ready
                        </Badge>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Active Requests */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">Active Requests</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {requests.length === 0 ? (
                    <div className="text-sm text-muted-foreground">
                      No active requests
                    </div>
                  ) : (
                    requests.map((req) => (
                      <div
                        key={req.request_id}
                        className="flex items-start justify-between rounded-lg border border-foreground/10 p-3"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <div className="font-mono text-xs text-muted-foreground">
                              {req.request_id.slice(0, 8)}
                            </div>
                            {getStatusBadge(req.status)}
                          </div>
                          <div className="mt-2 space-y-1 text-xs">
                            <div>
                              <span className="text-muted-foreground">
                                From:
                              </span>{" "}
                              {req.pickup_location}
                            </div>
                            <div>
                              <span className="text-muted-foreground">To:</span>{" "}
                              {req.dropoff_location}
                            </div>
                            {req.assigned_drone && (
                              <div>
                                <span className="text-muted-foreground">
                                  Drone:
                                </span>{" "}
                                {req.assigned_drone}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}
