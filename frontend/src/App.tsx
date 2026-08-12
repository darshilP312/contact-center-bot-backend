import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CommandCenter } from "./pages/CommandCenter";
import "./styles/index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 2, staleTime: 30_000 },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <CommandCenter />
    </QueryClientProvider>
  );
}
