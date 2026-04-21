// Accurate TypeScript types matching the Python TashiServer API responses.

export interface LocationOption {
  id: string
  label: string
  position: { x: number; y: number; z: number }
}

export interface LocationsResponse {
  pickup: LocationOption[]
  dropoff: LocationOption[]
}

export interface BidEntry {
  drone_id: string
  bid_price: number
  eta_minutes: number
  distance_meters: number
  timestamp: number
  confidence?: number
}

export interface MarketplaceRequest {
  request_id: string
  customer_id: string
  pickup: { x: number; y: number; z: number }
  dropoff: { x: number; y: number; z: number }
  pickup_location?: string
  dropoff_location?: string
  package_weight: number
  bid_deadline: number
  status: string
  bids: BidEntry[]
  awarded_drone?: string | null
  final_price?: number | null
  tracked_at?: number
  completed_at?: number
}

export interface ActiveRequestsResponse {
  active_requests: Record<string, MarketplaceRequest>
  total_active: number
}

export interface DroneCapabilities {
  max_payload: number
  max_range: number
  battery_capacity: number
  base_location: { x: number; y: number; z: number }
  reputation: number
}

export interface DroneState {
  id: string
  status: "idle" | "busy" | "error" | string
  current_request: string | null
  capabilities: DroneCapabilities
  reputation: number
  last_seen: number
}

export interface HistoryEntry extends MarketplaceRequest {
  status: "completed"
  completed_at: number
}

export interface HistoryResponse {
  history: HistoryEntry[]
  total_completed: number
  page: number
  limit: number
  total_pages: number
}

export interface ReputationScore {
  last_update: number
  event_type: string
  impact: number
}

export interface MarketplaceStatus {
  server_id: string
  connected: boolean
  active_requests: Record<string, MarketplaceRequest>
  delivery_history: HistoryEntry[]
  reputation_scores: Record<string, ReputationScore>
  drone_states: Record<string, DroneState>
  total_deliveries: number
  timestamp: number
}

// Normalized view model used across the UI
export interface DeliveryRequestView {
  request_id: string
  customer_id: string
  status: string
  pickup_location: string
  dropoff_location: string
  package_weight: number
  assigned_drone: string | null
  final_price: number | null
  bid_count: number
  created_at?: number
}
