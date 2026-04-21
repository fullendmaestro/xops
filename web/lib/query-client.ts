import { QueryClient } from "@tanstack/react-query"

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000, // 10s — data is fresh for 10 seconds
      refetchInterval: 15_000, // automatically refetch every 15 seconds
      retry: 2,
      refetchOnWindowFocus: true,
    },
    mutations: {
      retry: 1,
    },
  },
})
