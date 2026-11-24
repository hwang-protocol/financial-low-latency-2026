# Course run: Prometheus, Grafana and Loki

- RUN_ID: `20260722T043114Z-04-observability`
- Result: `PASS_OBSERVABILITY_THREE_STATE_AND_DASHBOARD`
- Prometheus: target state 1 → 0 → 1, then original config SHA restored
- Loki: normal, fault and recovered events pushed and queried
- Grafana: datasource and dashboard provisioning verified in the live Grafana storage
- Boundary: the endpoint and scrape job are temporary; the reusable dashboard remains provisioned
