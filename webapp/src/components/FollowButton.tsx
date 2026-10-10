import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { workflowApi } from "../api/client";

/** Follow a piece of equipment or a document: each change to it becomes a notification, in whichever
 *  workspace it is. Shown only to a signed-in person (an API-token profile follows nothing). */
export function FollowButton({ subject, uid }: { subject: "asset" | "document"; uid: string }) {
  const queryClient = useQueryClient();
  const state = useQuery({ queryKey: ["following", subject, uid], queryFn: () => workflowApi.following(subject, uid),
                           retry: false });
  const toggle = useMutation({
    mutationFn: (on: boolean) => workflowApi.follow(subject, uid, on),
    onSuccess: (s) => queryClient.setQueryData(["following", subject, uid], s),
  });
  if (!state.data) return null;
  const on = state.data.following;
  return (
    <button type="button" onClick={() => toggle.mutate(!on)} disabled={toggle.isPending}
            title={on ? "You are told of each change. Click to stop." : "Be told of each change to it, in any workspace."}
            className={`rounded-md border px-3 py-1.5 text-sm ${on
              ? "border-indigo-300 bg-indigo-50 text-indigo-800 hover:bg-indigo-100"
              : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"}`}>
      {on ? "🔔 Following" : "🔕 Follow"}
      {state.data.followers > (on ? 1 : 0) && (
        <span className="ml-1 text-xs text-slate-500">· {state.data.followers}</span>
      )}
    </button>
  );
}
