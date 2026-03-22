#!/usr/bin/env python3
"""Whanos Kubernetes deployer.

Reads whanos.yml from the current directory and generates + applies
Kubernetes manifests for the project.

Usage: deploy.py <project-name> <image-name>
"""

import json
import os
import subprocess
import sys

import yaml


def parse_whanos_yml(path="whanos.yml"):
    with open(path) as f:
        config = yaml.safe_load(f)
    return config.get("deployment", {})


def build_namespace(project):
    return {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {"name": project},
    }


def build_deployment(project, image, config):
    replicas = config.get("replicas", 1)
    ports = config.get("ports", [])
    resources = config.get("resources", {})
    env_vars = config.get("env", {})
    health = config.get("health_check", {})

    container = {
        "name": project,
        "image": image,
    }

    if ports:
        container["ports"] = [{"containerPort": p} for p in ports]

    if resources:
        container["resources"] = resources

    if env_vars:
        container["env"] = [{"name": k, "value": str(v)} for k, v in env_vars.items()]

    if health:
        probe = {
            "httpGet": {
                "path": health.get("path", "/health"),
                "port": health.get("port", ports[0] if ports else 80),
            },
            "initialDelaySeconds": health.get("initial_delay", 10),
            "periodSeconds": health.get("period", 30),
        }
        container["livenessProbe"] = probe
        container["readinessProbe"] = {
            **probe,
            "initialDelaySeconds": health.get("initial_delay", 5),
            "periodSeconds": health.get("period", 10),
        }

    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": project,
            "namespace": project,
        },
        "spec": {
            "replicas": replicas,
            "selector": {"matchLabels": {"app": project}},
            "template": {
                "metadata": {"labels": {"app": project}},
                "spec": {"containers": [container]},
            },
        },
    }


def build_service(project, config):
    ports = config.get("ports", [])
    if not ports:
        return None

    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": project,
            "namespace": project,
        },
        "spec": {
            "type": "LoadBalancer",
            "selector": {"app": project},
            "ports": [
                {"protocol": "TCP", "port": p, "targetPort": p} for p in ports
            ],
        },
    }


def build_ingress(project, config):
    ingress_config = config.get("ingress", {})
    if not ingress_config:
        return None

    host = ingress_config.get("host", f"{project}.local")
    ports = config.get("ports", [80])
    port = ports[0] if ports else 80

    rule = {
        "http": {
            "paths": [
                {
                    "path": "/",
                    "pathType": "Prefix",
                    "backend": {
                        "service": {
                            "name": project,
                            "port": {"number": port},
                        }
                    },
                }
            ]
        }
    }

    if host:
        rule["host"] = host

    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "metadata": {
            "name": f"{project}-ingress",
            "namespace": project,
        },
        "spec": {"rules": [rule]},
    }


def build_hpa(project, config):
    autoscale = config.get("autoscale", {})
    if not autoscale:
        return None

    return {
        "apiVersion": "autoscaling/v2",
        "kind": "HorizontalPodAutoscaler",
        "metadata": {
            "name": f"{project}-hpa",
            "namespace": project,
        },
        "spec": {
            "scaleTargetRef": {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "name": project,
            },
            "minReplicas": autoscale.get("min", 1),
            "maxReplicas": autoscale.get("max", 10),
            "metrics": [
                {
                    "type": "Resource",
                    "resource": {
                        "name": "cpu",
                        "target": {
                            "type": "Utilization",
                            "averageUtilization": autoscale.get("cpu_target", 70),
                        },
                    },
                }
            ],
        },
    }


def generate_manifests(project, image, config):
    manifests = [build_namespace(project), build_deployment(project, image, config)]

    service = build_service(project, config)
    if service:
        manifests.append(service)

    ingress = build_ingress(project, config)
    if ingress:
        manifests.append(ingress)

    hpa = build_hpa(project, config)
    if hpa:
        manifests.append(hpa)

    return manifests


def apply_manifests(manifests, dry_run=False):
    dumper = yaml.dumper.Dumper
    dumper.ignore_aliases = lambda self, data: True
    combined = "\n---\n".join(yaml.dump(m, default_flow_style=False, Dumper=dumper) for m in manifests)
    print("--- Generated Kubernetes manifests ---")
    print(combined)

    if dry_run:
        print("--- Dry run mode, skipping kubectl apply ---")
        return

    print("--- Applying manifests ---")
    result = subprocess.run(
        ["kubectl", "apply", "-f", "-"],
        input=combined,
        text=True,
        capture_output=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)


def main():
    dry_run = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--dry-run"]

    if len(args) < 2:
        print(f"Usage: {sys.argv[0]} <project-name> <image-name> [--dry-run]", file=sys.stderr)
        sys.exit(1)

    project = args[0]
    image = args[1]

    if not os.path.exists("whanos.yml"):
        print("No whanos.yml found, skipping deployment")
        sys.exit(0)

    config = parse_whanos_yml()
    manifests = generate_manifests(project, image, config)
    apply_manifests(manifests, dry_run=dry_run)
    print(f"Deployment of '{project}' complete.")


if __name__ == "__main__":
    main()
