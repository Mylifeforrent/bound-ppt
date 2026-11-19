import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { qk } from "@/api/keys";
import type { MaterialListDTO } from "@/api/types";

/** Current chips and the server-enforced cap for an existing project. */
export function useMaterials(projectId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: qk.materials(projectId ?? "none"),
    queryFn: async () => (await api<MaterialListDTO>(`/api/projects/${projectId}/materials`)).data,
    enabled: Boolean(projectId) && enabled,
    staleTime: 5_000,
  });
}
