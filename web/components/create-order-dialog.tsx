"use client"

import { useState } from "react"
import { AlertCircle } from "lucide-react"

import {
  useCreateOrder,
  useLocations,
  type CreateOrderPayload,
} from "@/lib/api/requests"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Field, FieldGroup } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

interface CreateOrderDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function CreateOrderDialog({
  open,
  onOpenChange,
}: CreateOrderDialogProps) {
  const { data: locations } = useLocations()
  const createOrder = useCreateOrder()

  const pickupOptions = locations?.pickup ?? []
  const dropoffOptions = locations?.dropoff ?? []

  const [customerId, setCustomerId] = useState("cust_001")
  const [pickupId, setPickupId] = useState("")
  const [dropoffId, setDropoffId] = useState("")
  const [weight, setWeight] = useState("1.0")

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    const payload: CreateOrderPayload = {
      customer_id: customerId,
      pickup: pickupId || (pickupOptions[0]?.id ?? ""),
      dropoff: dropoffId || (dropoffOptions[0]?.id ?? ""),
      package_weight: parseFloat(weight),
    }

    createOrder.mutate(payload, {
      onSuccess: () => {
        setWeight("1.0")
        onOpenChange(false)
      },
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <form onSubmit={(e) => void handleSubmit(e)}>
          <DialogHeader>
            <DialogTitle>Create order</DialogTitle>
            <DialogDescription>
              Where should the drone pick up and deliver?
            </DialogDescription>
          </DialogHeader>

          <FieldGroup className="mt-4">
            <Field>
              <Label htmlFor="dlg-customer-id">Customer ID</Label>
              <Input
                id="dlg-customer-id"
                value={customerId}
                onChange={(e) => setCustomerId(e.target.value)}
                placeholder="cust_001"
              />
            </Field>

            <FieldGroup className="grid grid-cols-2">
              <Field>
                <Label htmlFor="dlg-pickup">Pickup location</Label>
                <Select
                  value={pickupId || (pickupOptions[0]?.id ?? "")}
                  onValueChange={setPickupId}
                >
                  <SelectTrigger id="dlg-pickup" className="w-full">
                    <SelectValue placeholder="Select pickup" />
                  </SelectTrigger>
                  <SelectContent>
                    {pickupOptions.map((opt) => (
                      <SelectItem key={opt.id} value={opt.id}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>

              <Field>
                <Label htmlFor="dlg-dropoff">Dropoff location</Label>
                <Select
                  value={dropoffId || (dropoffOptions[0]?.id ?? "")}
                  onValueChange={setDropoffId}
                >
                  <SelectTrigger id="dlg-dropoff" className="w-full">
                    <SelectValue placeholder="Select dropoff" />
                  </SelectTrigger>
                  <SelectContent>
                    {dropoffOptions.map((opt) => (
                      <SelectItem key={opt.id} value={opt.id}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            </FieldGroup>

            <Field>
              <Label htmlFor="dlg-weight">Package weight (kg)</Label>
              <Input
                id="dlg-weight"
                type="number"
                step="0.1"
                min="0.1"
                value={weight}
                onChange={(e) => setWeight(e.target.value)}
                placeholder="1.0"
              />
            </Field>
          </FieldGroup>

          {createOrder.isError && (
            <div className="mt-4 flex gap-2 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              <AlertCircle className="size-4 shrink-0" />
              <span>
                {createOrder.error instanceof Error
                  ? createOrder.error.message
                  : "Network error"}
              </span>
            </div>
          )}

          <DialogFooter className="mt-4">
            <DialogClose asChild>
              <Button variant="outline">Cancel</Button>
            </DialogClose>
            <Button type="submit" disabled={createOrder.isPending}>
              {createOrder.isPending ? "Creating..." : "Create order"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
