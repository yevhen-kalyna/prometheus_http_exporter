# Prometheus HTTP Exporter

## Description

Prometheus exporter for gathering NGINX ingress endpoints by regex and check their status code using http path.

Metrics can be served or/and can be pushed to Prometheus Gateway.

Metics name: `http_exporter_probe_http_status_code`

## Configuration

Example of `config` in `./chart/values.yaml`

```yaml
# Prometheus HTTP Exporter configuration file.
config:
  publish_port: 8000 # [Optional] Serving port, here you can see your metrics, default 8000
  check_delay: 5 # [Optional] How often we should check enpoints, in seconds, default 5
  push_gateway: # [Optional] Prometheus Pushgateway configuration
    address: prometheus-pushgateway:9091 # Address of Prometheus Pushgateway
    job: prometheus_http_exporter # [Optional] Metric label
  targets: # List of targets to gather and check
  - pattern: ^api.* # Regular expresion which will find your Ingress Host
    path: /swagger-ui.html # Path to check in each finded Ingress Host
    follow_redirects: true # [Optional] Should we follow redirects, default True
    insecure_skip_verify: true # [Optional] Should we check secure connection or not, default False
    timeout: 5 # [Optional] Fail if can't connect to URL after N seconds, default 5
```

## Usage

### Reguirenments

- Kubernetes Cluster 1.16+
- Helm 3+
- [Optional] Prometheus Gateway in K8S cluster
- [Optional] Grafana

### Steps

1. Clone repository: `git clone git@github.com:yevhen-kalyna/prometheus_http_exporter.git`
2. Enter in it: `cd prometheus_http_exporter`
3. Change chart values: `nano ./chart/values.yaml`
4. Install Helm chart in your cluster: `helm install prometheus-http-exporter -n <YOUR_NAMESPACE> ./chart`
   1. [Optional] Or if installed, upgrade chart with: `helm upgrade prometheus-http-exporter -n monitoring ./chart`
5. [Optional] Check your new metrics in your Prometheus via name: `http_exporter_probe_http_status_code`
6. [Optional] If your Prometheus connected as datasourse to Grafana, you can query them: e.x. `count by (url) (http_exporter_probe_http_status_code{url=~ ".*api[.].*"} == 200)`
