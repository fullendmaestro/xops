import { randomUUID } from "node:crypto"
import type { CreateOrderInput, DeliveryOrder } from "@/lib/models/order"

type StoreShape = {
  orders: DeliveryOrder[]
}

declare global {
  // eslint-disable-next-line no-var
  var __xopsOrderStore: StoreShape | undefined
}

const store: StoreShape = globalThis.__xopsOrderStore ?? { orders: [] }

if (!globalThis.__xopsOrderStore) {
  globalThis.__xopsOrderStore = store
}

export function listOrders(): DeliveryOrder[] {
  return [...store.orders].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
  )
}

export function createOrder(input: CreateOrderInput): DeliveryOrder {
  const createdAt = new Date().toISOString()
  const order: DeliveryOrder = {
    id: randomUUID(),
    customerName: input.customerName,
    item: input.item,
    pickup: input.pickup,
    dropoff: input.dropoff,
    payloadKg: input.payloadKg,
    budgetUsd: input.budgetUsd,
    priority: input.priority,
    status: "submitted",
    createdAt,
  }

  store.orders.push(order)
  return order
}
