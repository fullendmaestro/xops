"use client"

import { useEffect, useMemo, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

const API_BASE = "http://localhost:5000"

type LocationOption = {
  id: string
  label: string
  position: { x: number; y: number; z: number }
}

type RequestRecord = {
  request_id: string
  customer_id: string
  package_weight: number
  pickup: { x: number; y: number; z: number }
  dropoff: { x: number; y: number; z: number }
  status: string
  awarded_drone?: string
  final_price?: number
}

type DroneRecord = {
  id: string
  capabilities: {
    max_payload: number
    max_range: number
    battery_capacity: number
    reputation: number
  }
}

function LocationChip({ location }: { location: { x: number; y: number; z: number } }) {
  return (
    <span className="rounded-full border border-zinc-800 bg-zinc-900 px-2.5 py-1 text-xs text-zinc-300">
      ({location.x.toFixed(1)}, {location.y.toFixed(1)}, {location.z.toFixed(1)})
    </span>
  )
}

export default function Home() {
  const [pickupOptions, setPickupOptions] = useState<LocationOption[]>([])
  const [dropoffOptions, setDropoffOptions] = useState<LocationOption[]>([])
  const [requests, setRequests] = useState<Record<string, RequestRecord>>({})
  const [drones, setDrones] = useState<Record<string, DroneRecord>>({})

  const [customerId, setCustomerId] = useState("customer_001")
  const [pickupId, setPickupId] = useState("")
  const [dropoffId, setDropoffId] = useState("")
  const [weight, setWeight] = useState("2.5")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const statusSummary = useMemo(() => {
    const list = Object.values(requests)
    const pending = list.filter((item) => item.status === "pending").length
    const awarded = list.filter((item) => item.status === "awarded").length
    return { total: list.length, pending, awarded }
  }, [requests])

  useEffect(() => {
    const loadInitial = async () => {
      try {
        const [locationRes, requestRes, droneRes] = await Promise.all([
          fetch(`${API_BASE}/api/locations`),
          fetch(`${API_BASE}/api/requests`),
          fetch(`${API_BASE}/api/drones`),
        ])

        if (!locationRes.ok || !requestRes.ok || !droneRes.ok) {
          throw new Error("Could not reach xops web client API")
        }

        const locationData = await locationRes.json()
        setPickupOptions(locationData.pickup ?? [])
        setDropoffOptions(locationData.dropoff ?? [])

        if (!pickupId && locationData.pickup?.[0]?.id) {
          setPickupId(locationData.pickup[0].id)
        }
        if (!dropoffId && locationData.dropoff?.[0]?.id) {
          setDropoffId(locationData.dropoff[0].id)
        }

        const requestData = await requestRes.json()
        setRequests(requestData.active_requests ?? {})

        const droneData = await droneRes.json()
        setDrones(droneData ?? {})
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load dashboard data")
      }
    }

    loadInitial()
    const timer = window.setInterval(loadInitial, 1800)
    return () => window.clearInterval(timer)
  }, [pickupId, dropoffId])

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setIsSubmitting(true)
    setError(null)

    try {
      const payload = {
        customer_id: customerId.trim(),
        pickup_id: pickupId,
        dropoff_id: dropoffId,
        package_weight: Number(weight),
      }

      const response = await fetch(`${API_BASE}/api/requests`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })

      const body = await response.json()
      if (!response.ok) {
        throw new Error(body.error ?? "Unable to submit request")
      }

      setCustomerId((prev) => (prev === "customer_001" ? "customer_002" : prev))
      setWeight("2.5")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit request")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_0%_0%,#334155_0,#0f172a_45%,#020617_100%)] p-4 text-zinc-100 md:p-8">
      <main className="mx-auto grid max-w-6xl gap-4 md:grid-cols-[1.1fr_1fr]">
        <Card className="border-zinc-800/80 bg-zinc-950/85">
          <CardHeader>
            <CardTitle className="text-xl tracking-wide text-cyan-300">XOPS Dispatch Console</CardTitle>
            <CardDescription className="text-zinc-400">
              Submit a delivery request with predefined pickup and drop-off pads.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="grid gap-4" onSubmit={onSubmit}>
              <div className="grid gap-1.5">
                <Label htmlFor="customer-id">Customer ID</Label>
                <Input
                  id="customer-id"
                  value={customerId}
                  onChange={(event) => setCustomerId(event.target.value)}
                  placeholder="customer_001"
                  required
                />
              </div>

              <div className="grid gap-1.5">
                <Label>Pickup Point</Label>
                <Select value={pickupId} onValueChange={setPickupId}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select pickup" />
                  </SelectTrigger>
                  <SelectContent>
                    {pickupOptions.map((item) => (
                      <SelectItem key={item.id} value={item.id}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-1.5">
                <Label>Drop-off Point</Label>
                <Select value={dropoffId} onValueChange={setDropoffId}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select drop-off" />
                  </SelectTrigger>
                  <SelectContent>
                    {dropoffOptions.map((item) => (
                      <SelectItem key={item.id} value={item.id}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-1.5">
                <Label htmlFor="weight">Package Weight (kg)</Label>
                <Input
                  id="weight"
                  type="number"
                  min="0.1"
                  step="0.1"
                  value={weight}
                  onChange={(event) => setWeight(event.target.value)}
                  required
                />
              </div>

              <Button disabled={isSubmitting || !pickupId || !dropoffId} type="submit" className="h-10">
                {isSubmitting ? "Submitting..." : "Submit Delivery Request"}
              </Button>
              {error ? <p className="text-sm text-rose-300">{error}</p> : null}
            </form>
          </CardContent>
        </Card>

        <div className="grid gap-4">
          <Card className="border-zinc-800/80 bg-zinc-950/85">
            <CardHeader>
              <CardTitle className="text-base text-zinc-200">Live Marketplace Snapshot</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-3 gap-3">
              <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-3">
                <p className="text-xs text-zinc-400">Total Requests</p>
                <p className="text-2xl font-semibold text-cyan-300">{statusSummary.total}</p>
              </div>
              <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-3">
                <p className="text-xs text-zinc-400">Pending Bids</p>
                <p className="text-2xl font-semibold text-amber-300">{statusSummary.pending}</p>
              </div>
              <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-3">
                <p className="text-xs text-zinc-400">Awarded</p>
                <p className="text-2xl font-semibold text-emerald-300">{statusSummary.awarded}</p>
              </div>
            </CardContent>
          </Card>

          <Card className="border-zinc-800/80 bg-zinc-950/85">
            <CardHeader>
              <CardTitle className="text-base text-zinc-200">Drone Fleet</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-2">
              {Object.values(drones).map((drone) => (
                <div key={drone.id} className="rounded-lg border border-zinc-800 bg-zinc-900 p-3">
                  <div className="flex items-center justify-between">
                    <p className="font-medium text-cyan-200">{drone.id}</p>
                    <Badge variant="outline">Rep {drone.capabilities.reputation.toFixed(1)}</Badge>
                  </div>
                  <p className="mt-1 text-xs text-zinc-400">
                    Payload {drone.capabilities.max_payload}kg • Range {drone.capabilities.max_range}m
                  </p>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        <Card className="border-zinc-800/80 bg-zinc-950/85 md:col-span-2">
          <CardHeader>
            <CardTitle className="text-base text-zinc-200">Active Requests</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2">
            {Object.values(requests).length === 0 ? (
              <p className="text-sm text-zinc-400">No active requests yet.</p>
            ) : (
              Object.values(requests).map((item) => (
                <article key={item.request_id} className="rounded-lg border border-zinc-800 bg-zinc-900 p-3">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <h2 className="font-medium text-zinc-200">{item.request_id}</h2>
                    <Badge variant={item.status === "awarded" ? "secondary" : "outline"}>{item.status}</Badge>
                  </div>
                  <p className="mb-2 text-xs text-zinc-400">
                    Customer {item.customer_id} • {item.package_weight}kg
                  </p>
                  <div className="flex flex-wrap gap-2 text-xs text-zinc-300">
                    <LocationChip location={item.pickup} />
                    <span className="self-center text-zinc-500">to</span>
                    <LocationChip location={item.dropoff} />
                  </div>
                  {item.awarded_drone ? (
                    <p className="mt-2 text-xs text-emerald-300">
                      Awarded to {item.awarded_drone} for ${item.final_price?.toFixed(2)}
                    </p>
                  ) : null}
                </article>
              ))
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
