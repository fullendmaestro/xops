// Re-export from the unified marketplace model for backward compat with
// order-table.tsx which still imports DeliveryRequest from here.
export type { LocationOption, DroneState as Drone } from "@/lib/models/marketplace"

// Normalized view-model used in the Orders table
export interface DeliveryRequest {
  request_id: string
  customer_id: string
  status: string
  pickup_location: string
  dropoff_location: string
  package_weight: number
  assigned_drone: string | null
  final_price?: number | null
  bid_count?: number
  created_at?: number
}
