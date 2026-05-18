import type { QueryClient } from "@tanstack/react-query";

export function invalidateLearningQueries(queryClient: QueryClient) {
  void queryClient.invalidateQueries({ queryKey: ["learner-profile"] });
  void queryClient.invalidateQueries({ queryKey: ["learner-profile-evidence"] });
  void queryClient.invalidateQueries({ queryKey: ["learner-evidence-ledger"] });
  void queryClient.invalidateQueries({ queryKey: ["learning-effect-report"] });
  void queryClient.invalidateQueries({ queryKey: ["learning-effect-concepts"] });
  void queryClient.invalidateQueries({ queryKey: ["learning-effect-next-actions"] });
}
