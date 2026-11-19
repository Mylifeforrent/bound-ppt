import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { qk } from "@/api/keys";
import type { NoticeDTO } from "@/api/types";

export function usePolicyNotices() {
  return useQuery({
    queryKey: qk.notices,
    queryFn: async () => (await api<{ notices: NoticeDTO[] }>("/api/policy/notices")).data.notices,
    staleTime: 5 * 60_000,
    retry: 1,
  });
}

export async function acceptPolicyNotice(notice: NoticeDTO, idempotencyKey: string): Promise<{ acceptedAt: string; version: string }> {
  const { data } = await api<{ acceptedAt: string; version: string }>("/api/policy/consent", {
    method: "POST",
    body: { noticeType: notice.type, version: notice.version },
    idempotencyKey,
  });
  return data;
}
