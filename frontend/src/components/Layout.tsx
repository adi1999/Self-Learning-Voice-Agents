import { NavLink } from 'react-router-dom'
import { type ReactNode } from 'react'
import { Users, Dna, MessageSquare, Archive, Mic, BookOpen, BarChart3, FileText } from 'lucide-react'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarProvider,
  SidebarInset,
} from '@/components/ui/sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'

const navItems = [
  { to: '/', label: 'Story', icon: BarChart3 },
  { to: '/personas', label: 'Personas', icon: Users },
  { to: '/evolution', label: 'Evolution', icon: Dna },
  { to: '/conversations', label: 'Conversations', icon: MessageSquare },
  { to: '/archive', label: 'Archive', icon: Archive },
  { to: '/voice', label: 'Voice Agent', icon: Mic },
  { to: '/prompt', label: 'Agent Prompt', icon: FileText },
  { to: '/playbook', label: 'Playbook', icon: BookOpen },
]

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <TooltipProvider>
      <SidebarProvider>
        <Sidebar>
          <SidebarHeader className="px-4 py-5 border-b border-sidebar-border">
            <h1 className="text-base font-semibold text-sidebar-foreground">Darwin-Godel</h1>
            <p className="text-xs text-sidebar-foreground/50 mt-0.5">Voice Agent Evolution</p>
          </SidebarHeader>
          <SidebarContent>
            <SidebarMenu className="py-2">
              {navItems.map(item => (
                <SidebarMenuItem key={item.to}>
                  <NavLink to={item.to} end={item.to === '/'}>
                    {({ isActive }) => (
                      <SidebarMenuButton
                        isActive={isActive}
                        className="w-full"
                      >
                        <item.icon className="size-4" />
                        <span>{item.label}</span>
                      </SidebarMenuButton>
                    )}
                  </NavLink>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarContent>
          <SidebarFooter className="px-4 py-3 border-t border-sidebar-border">
            <p className="text-xs text-sidebar-foreground/40">Self-Learning Voice Agents</p>
          </SidebarFooter>
        </Sidebar>
        <SidebarInset>
          <main className="flex-1 overflow-y-auto p-6">
            {children}
          </main>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  )
}
