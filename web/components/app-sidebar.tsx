import {
  BarChart3,
  Bell,
  CircleDot,
  ClipboardList,
  Container,
  LayoutDashboard,
  Package,
  ShieldCheck,
  Truck,
  Users,
  Waypoints,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
} from "@/components/ui/sidebar"

const navigation = [
  { label: "Dashboard", icon: LayoutDashboard },
  { label: "Orders", icon: ClipboardList, badge: "12" },
  { label: "Fleet", icon: Truck },
  { label: "Bids", icon: CircleDot },
  { label: "Reputation", icon: ShieldCheck },
]

const secondaryNavigation = [
  { label: "Analytics", icon: BarChart3 },
  { label: "Customers", icon: Users },
  { label: "Waypoints", icon: Waypoints },
  { label: "Packages", icon: Package },
]

export function AppSidebar() {
  return (
    <Sidebar variant="inset" collapsible="icon">
      <SidebarHeader className="gap-3 border-b border-sidebar-border/70 p-4">
        <div className="flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-xl bg-sidebar-primary text-sidebar-primary-foreground shadow-sm">
            <Container className="size-4" />
          </div>
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">XOPS</div>
            <div className="truncate text-xs text-sidebar-foreground/70">
              Drone delivery control plane
            </div>
          </div>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>General</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navigation.map((item, index) => (
                <SidebarMenuItem key={item.label}>
                  <SidebarMenuButton
                    isActive={index === 0}
                    tooltip={item.label}
                    className="justify-start"
                  >
                    <item.icon />
                    <span>{item.label}</span>
                    {item.badge && (
                      <Badge
                        variant="secondary"
                        className="ml-auto h-5 rounded-full px-1.5 text-[10px]"
                      >
                        {item.badge}
                      </Badge>
                    )}
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator />

        <SidebarGroup>
          <SidebarGroupLabel>Operations</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {secondaryNavigation.map((item) => (
                <SidebarMenuItem key={item.label}>
                  <SidebarMenuButton
                    tooltip={item.label}
                    className="justify-start"
                  >
                    <item.icon />
                    <span>{item.label}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="mt-auto border-t border-sidebar-border/70 p-4">
        <div className="flex items-center justify-between rounded-xl border border-sidebar-border bg-sidebar-accent/50 px-3 py-2">
          <div>
            <div className="text-sm font-medium">Swarm online</div>
            <div className="text-xs text-sidebar-foreground/70">
              Live request sync enabled
            </div>
          </div>
          <Bell className="size-4 text-sidebar-foreground/70" />
        </div>
      </SidebarFooter>
    </Sidebar>
  )
}
