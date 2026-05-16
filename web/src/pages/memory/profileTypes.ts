import type { LearnerProfileCalibrationRequest } from "@/lib/types";

export type CalibrateProfile = (input: LearnerProfileCalibrationRequest) => Promise<void>;
