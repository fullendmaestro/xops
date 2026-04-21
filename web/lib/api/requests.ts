import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import type {
  ActiveRequestsResponse,
  DeliveryRequestView,
  DroneState,
  HistoryResponse,
  LocationsResponse,
  MarketplaceRequest,
  MarketplaceStatus,
} from "@/lib/models/marketplace"

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000"

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { error?: string }).error ?? `API error ${res.status}`)
  }
  return res.json() as Promise<T>
}

// ---- Query keys ----
export const queryKeys = {
  requests: ["requests"] as const,
  drones: ["drones"] as const,
  locations: ["locations"] as const,
  history: (page: number, limit: number) => ["history", page, limit] as const,
  status: ["status"] as const,
}

// ---- Normalizer ----
function formatPos(pos?: { x: number; y: number; z: number }) {
  if (!pos) return "Unknown"
  return `${pos.x.toFixed(1)}, ${pos.y.toFixed(1)}, ${pos.z.toFixed(1)}`
}

function normalizeRequest(
  requestId: string,
  raw: MarketplaceRequest,
): DeliveryRequestView {
  return {
    request_id: raw.request_id ?? requestId,
    customer_id: raw.customer_id ?? "unknown",
    status: raw.status ?? "pending",
    pickup_location: raw.pickup_location ?? formatPos(raw.pickup),
    dropoff_location: raw.dropoff_location ?? formatPos(raw.dropoff),
    package_weight: Number(raw.package_weight ?? 0),
    assigned_drone: raw.awarded_drone ?? null,
    final_price: raw.final_price ?? null,
    bid_count: raw.bids?.length ?? 0,
    created_at: raw.tracked_at,
  }
}

// ---- Hooks ----

export function useRequests() {
  return useQuery({
    queryKey: queryKeys.requests,
    queryFn: async () => {
      const data = await apiFetch<ActiveRequestsResponse>("/api/requests")
      const raw = data.active_requests ?? {}
      return Object.entries(raw).map(([id, req]) => normalizeRequest(id, req))
    },
  })
}

export function useDrones() {
  return useQuery({
    queryKey: queryKeys.drones,
    queryFn: () => apiFetch<DroneState[]>("/api/drones"),
  })
}

export function useLocations() {
  return useQuery({
    queryKey: queryKeys.locations,
    queryFn: () => apiFetch<LocationsResponse>("/api/locations"),
    staleTime: Infinity, // locations don't change at runtime
    refetchInterval: false,
  })
}

export function useOrderHistory(page = 1, limit = 20) {
  return useQuery({
    queryKey: queryKeys.history(page, limit),
    queryFn: () =>
      apiFetch<HistoryResponse>(
        `/api/history?page=${page}&limit=${limit}`,
      ),
  })
}

export function useMarketplaceStatus() {
  return useQuery({
    queryKey: queryKeys.status,
    queryFn: () => apiFetch<MarketplaceStatus>("/api/status"),
  })
}

export interface CreateOrderPayload {
  customer_id: string
  pickup: string
  dropoff: string
  package_weight: number
}

export function useCreateOrder() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: CreateOrderPayload) => {
      const res = await fetch(`${API_BASE_URL}/api/requests`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(
          (err as { error?: string }).error ?? "Request failed",
        )
      }
      return res.json()
    },
    onSuccess: () => {
      // Immediately refetch active requests & status after submitting
      void qc.invalidateQueries({ queryKey: queryKeys.requests })
      void qc.invalidateQueries({ queryKey: queryKeys.status })
    },
  })
}
