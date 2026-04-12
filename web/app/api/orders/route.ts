import { NextResponse } from "next/server"
import { createOrder, listOrders } from "@/lib/server/order-store"
import type { CreateOrderInput } from "@/lib/models/order"

function isValidCoordinate(value: unknown): value is { lat: number; lng: number } {
  if (!value || typeof value !== "object") {
    return false
  }

  const candidate = value as { lat?: unknown; lng?: unknown }
  return typeof candidate.lat === "number" && typeof candidate.lng === "number"
}

function validateInput(raw: unknown): { valid: true; data: CreateOrderInput } | { valid: false; message: string } {
  if (!raw || typeof raw !== "object") {
    return { valid: false, message: "Request body must be a JSON object." }
  }

  const body = raw as Record<string, unknown>

  if (typeof body.customerName !== "string" || body.customerName.trim().length < 2) {
    return { valid: false, message: "customerName must be at least 2 characters." }
  }

  if (typeof body.item !== "string" || body.item.trim().length < 2) {
    return { valid: false, message: "item must be at least 2 characters." }
  }

  if (!isValidCoordinate(body.pickup) || !isValidCoordinate(body.dropoff)) {
    return { valid: false, message: "pickup and dropoff coordinates are required." }
  }

  if (typeof body.payloadKg !== "number" || body.payloadKg <= 0) {
    return { valid: false, message: "payloadKg must be greater than 0." }
  }

  if (typeof body.budgetUsd !== "number" || body.budgetUsd <= 0) {
    return { valid: false, message: "budgetUsd must be greater than 0." }
  }

  if (body.priority !== "low" && body.priority !== "medium" && body.priority !== "high") {
    return { valid: false, message: "priority must be low, medium, or high." }
  }

  return {
    valid: true,
    data: {
      customerName: body.customerName.trim(),
      item: body.item.trim(),
      pickup: body.pickup,
      dropoff: body.dropoff,
      payloadKg: body.payloadKg,
      budgetUsd: body.budgetUsd,
      priority: body.priority,
    },
  }
}

export async function GET() {
  return NextResponse.json({ orders: listOrders() })
}

export async function POST(request: Request) {
  const payload = await request.json().catch(() => null)
  const parsed = validateInput(payload)

  if (!parsed.valid) {
    return NextResponse.json({ error: parsed.message }, { status: 400 })
  }

  const created = createOrder(parsed.data)
  return NextResponse.json({ order: created }, { status: 201 })
}
