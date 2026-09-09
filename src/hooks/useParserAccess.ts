import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../services/apiClient";

export function useParserAccess() {
  const { data } = useQuery({
    queryKey: ["parser-access"],
    queryFn: () => apiRequest<{ public_enabled: boolean }>("/api/extract/access"),
    staleTime: 0,
    refetchInterval: 30_000,
  });
  return data?.public_enabled === true;
}
