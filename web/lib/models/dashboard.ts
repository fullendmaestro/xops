export interface LocationOption {
  id: string
  label: string
  position: { x: number; y: number; z: number }
}

export interface Drone {
  id: string
  name: string
  status: string
  battery_level: number
  location: { x: number; y: number; z: number }
}

export interface DeliveryRequest {
  request_id: string
  customer_id: string
  status: string
  pickup_location: string
  dropoff_location: string
  package_weight: number
  assigned_drone: string | null
}
