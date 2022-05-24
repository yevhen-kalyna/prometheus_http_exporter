from time import sleep
from typing import Any, List, Optional
from urllib.error import URLError
import requests
from prometheus_client import start_http_server, Gauge, push_to_gateway, REGISTRY
from loguru import logger
import confuse
from kubernetes import client, config
import re
import urllib3
from pydantic import BaseModel, parse_obj_as, ValidationError


def load_k8s_config():
    try:
        try:
            config.load_kube_config(config_file="~/.kube/config")
        except config.config_exception.ConfigException:
            config.load_incluster_config()
    except Exception as e:
        logger.exception(e)
        logger.error("Can\'t find kubernetes config file, It will initially try to load_kube_config from '~/.kube/config' path, then check if the KUBE_CONFIG_DEFAULT_LOCATION exists If neither exists, it will fall back to load_incluster_config and inform the user accordingly.")
    return client.NetworkingV1Api()


class Target(BaseModel):
    pattern: str
    path: str
    urls: List[str] = []
    follow_redirects: bool = True
    insecure_skip_verify: bool = False
    timeout: int = 5


class PushGateway(BaseModel):
    address: str = "localhost:9091"
    job: str = "prometheus_http_exporter"
    registry: Optional[Any] = None


class Configuration(BaseModel):
    publish_port: int = 8000
    check_delay: int = 5
    push_gateway: PushGateway
    targets: List[Target] = []


def load_configuration(config_file: str = "config.yaml"):
    try:
        raw_configuration = confuse.Configuration("prometheus_http_exporter")
        raw_configuration.set_file(config_file)
        try:
            push_gateway = parse_obj_as(
                PushGateway, raw_configuration["push_gateway"].get())
        except confuse.NotFoundError:
            push_gateway = PushGateway()
        try:
            check_delay = raw_configuration["check_delay"].get()
        except confuse.NotFoundError:
            check_delay = 5
        try:
            publish_port = raw_configuration["publish_port"].get()
        except confuse.NotFoundError:
            publish_port = 8000

        configuration = Configuration(
            push_gateway=push_gateway,
            check_delay=check_delay,
            publish_port=publish_port,
            targets=parse_obj_as(
                List[Target], raw_configuration["targets"].get())
        )

        if not configuration.push_gateway.registry:
            configuration.push_gateway.registry = REGISTRY

        return configuration  # noqa
    except confuse.exceptions.ConfigReadError as e:
        logger.exception(e)
        logger.error("Can\'t find \"config.yaml\", is it exists?")
    except ValidationError as e:
        logger.exception(e)
        logger.error("Invalid config file fields.")


def update_target_urls(target: Target, networking_v1_api: client.NetworkingV1Api()) -> Target:
    all_ingreses = networking_v1_api.list_ingress_for_all_namespaces().items
    hosts = []

    for ingress in all_ingreses:
        rules = ingress.spec.rules
        if rules:
            for rule in rules:
                if rule.host:
                    hosts.append(rule.host)

    for host in hosts:
        if re.match(target.pattern, host):
            target_url = "http://" + host
            if target.path:
                target_url += target.path
            target.urls.append(target_url)
    return target


def validate_target(gauge_metric: Gauge, target: Target, configuration: Configuration):
    for target_url in target.urls:
        try:
            responce = requests.get(target_url, verify=not target.insecure_skip_verify,
                                    allow_redirects=target.follow_redirects, timeout=target.timeout)
        except requests.exceptions.ReadTimeout:
            logger.warning(f"Request timeout for {target_url}")
        except Exception as e:
            logger.error(
                f"Error occure on get request to target url {target_url}")
            logger.exception(e)

        gauge_metric.labels(target_url, target.pattern,
                            target.path).set(responce.status_code)
        if configuration.push_gateway.registry:
            try:
                push_to_gateway(configuration.push_gateway.address,
                                job=configuration.push_gateway.job, registry=configuration.push_gateway.registry)
            except URLError:
                logger.error("Can\'t connect to pushgateway!")
                logger.exception(e)
                exit(1)
            except Exception as e:
                logger.exception(e)

@logger.catch
def main():
    urllib3.disable_warnings()
    
    networking_v1_api = load_k8s_config()
    configuration = load_configuration("/config/config.yaml")

    gauge_metric = Gauge("http_exporter_probe_http_status_code",
                         "Status code of request to URL",
                         ["url", "pattern", "path"],
                         registry=configuration.push_gateway.registry
                         )

    start_http_server(configuration.publish_port)
    logger.info(f"Starting HTTP server at http://localhost:{configuration.publish_port}")

    while True:
        for target in configuration.targets:
            target = update_target_urls(target, networking_v1_api)
            if target.urls:
                validate_target(gauge_metric, target, configuration)
        sleep(configuration.check_delay)

if __name__ == "__main__":
    main()
