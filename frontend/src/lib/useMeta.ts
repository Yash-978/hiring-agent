import { useQuery } from "@tanstack/react-query";
import { getMeta } from "@/api/client";
import type { MetaInfo } from "@/api/types";

export function useMeta() {
  return useQuery<MetaInfo>({
    queryKey: ["meta"],
    queryFn: getMeta,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
}
