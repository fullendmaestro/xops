export type OrderPriority = "low" | "medium" | "high"

export type OrderStatus = "submitted" | "assigned" | "in_transit" | "completed"

export interface Coordinates {
  lat: number
  lng: number
}

export interface DeliveryOrder {
  id: string
  customerName: string
  item: string
  pickup: Coordinates
  dropoff: Coordinates
  payloadKg: number
  budgetUsd: number
  priority: OrderPriority
  status: OrderStatus
  createdAt: string
  assignedDroneId?: string
  assignedAt?: string
  estimatedMinutes?: number
  dispatchScore?: number
}

export interface CreateOrderInput {
  customerName: string
  item: string
  pickup: Coordinates
  dropoff: Coordinates
  payloadKg: number
  budgetUsd: number
  priority: OrderPriority
}
