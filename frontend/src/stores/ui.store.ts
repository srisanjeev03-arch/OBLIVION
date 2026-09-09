import { create } from 'zustand'

export type DrawerType = 'operation' | 'target' | 'residual' | 'certificate' | 'audit' | null

interface UIState {
  activeDrawer: DrawerType
  drawerPayload: unknown
  activeOperationId: string | null
  selectedTargetId: string | null
  offlineDemoMode: boolean
  openDrawer: (type: DrawerType, payload?: unknown) => void
  closeDrawer: () => void
  setActiveOperationId: (id: string | null) => void
  setSelectedTargetId: (id: string | null) => void
  setOfflineDemoMode: (enabled: boolean) => void
}

export const useUIStore = create<UIState>((set) => ({
  activeDrawer: null,
  drawerPayload: null,
  activeOperationId: null,
  selectedTargetId: null,
  offlineDemoMode: false,
  openDrawer: (type, payload = null) => set({ activeDrawer: type, drawerPayload: payload }),
  closeDrawer: () => set({ activeDrawer: null, drawerPayload: null }),
  setActiveOperationId: (id) => set({ activeOperationId: id }),
  setSelectedTargetId: (id) => set({ selectedTargetId: id }),
  setOfflineDemoMode: (enabled) => set({ offlineDemoMode: enabled }),
}))
