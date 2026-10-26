#pragma once
// EXPERIMENTAL fallback scales. They are NOT CALIBRATED: replace with
// statistics from representative chess positions before production use.
// Values must be positive. INT8 clipping must be inspected during validation.
#ifndef PA56_TRUNK_SCALE
#define PA56_TRUNK_SCALE (1.0f / 16.0f)
#endif
#ifndef PA56_RES1_SCALE
#define PA56_RES1_SCALE (1.0f / 16.0f)
#endif
