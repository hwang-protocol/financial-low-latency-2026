# Course run: logical Feed A/B and Feed Handler

- RUN_ID: `20260722T042030Z-03-feed-ab`
- Result: `PASS_LOGICAL_FEED_AB_HANDLER`
- Membership: pre-join 0, joined delivery, post-leave 0
- Merge: final sequence 0..5; Feed A omitted 4; Feed B recovered 4
- Duplicate rule: first valid copy wins; later copy is suppressed
- Boundary: two logical groups share VM1 NIC, VM2 NIC and the same Arista fabric; this is not physical A/B isolation
