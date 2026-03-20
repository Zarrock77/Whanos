# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Whanos is an Epitech DevOps project that sets up an infrastructure to automatically deploy applications into a Kubernetes cluster on a Git push. It combines Docker, Jenkins, Ansible, and Kubernetes to provide a complete CI/CD pipeline supporting C, Java, JavaScript, Python, and Befunge.

**Pipeline flow:** Git push → Jenkins detects change → auto-detect language → containerize with Whanos image → push to Docker registry → deploy to Kubernetes (if `whanos.yml` present).

## Architecture

### Docker Images (`images/`)

Two image types per language, in `images/<language>/`:
- **`Dockerfile.base`** — Built standalone without app code (`docker build -t whanos-<lang> - < Dockerfile.base`). Used as `FROM` target when apps provide their own Dockerfile.
- **`Dockerfile.standalone`** — Complete self-contained image. Used when apps have **no** Dockerfile at their root.

**Language detection** (mutually exclusive — a repo must match exactly one):

| Language   | Detection file        | Base image name      | Execution command       |
|------------|-----------------------|----------------------|-------------------------|
| C          | `Makefile`            | `whanos-c`           | `./compiled-app`        |
| Java       | `app/pom.xml`         | `whanos-java`        | `java -jar app.jar`     |
| JavaScript | `package.json`        | `whanos-javascript`  | `node .`                |
| Python     | `requirements.txt`    | `whanos-python`      | `python -m app`         |
| Befunge    | `app/main.bf`         | `whanos-befunge`     | Free choice             |

App source code lives in the `app/` directory of Whanos-compatible repositories.

### Jenkins (`jenkins/`)

- `config.yml` — Jenkins Configuration as Code (JCasC). RBAC with admin users: admin, jj, wast, ak. Sign-up disabled.
- `jobs.groovy` — Job DSL script defining:
  - **"Whanos base images"** folder with per-language build jobs + "Build all base images" trigger
  - **"Projects"** folder for linked project jobs
  - **`link-project`** root job — accepts Git URL + project name, creates a job that polls every minute and auto-builds/deploys

### Ansible (`ansible/`)

Deploys the full infrastructure via `ansible-playbook -i inventories/host site.yml`.

Roles executed in order:
1. `docker` — installs Docker runtime
2. `jenkins` — installs Java + Jenkins, configures admin
3. `kubernetes` — installs kubeadm/kubectl/kubelet, initializes cluster with Calico CNI
4. `whanos` — builds all base and standalone Docker images

### Kubernetes (`kubernetes/`)

Template manifests for deployed apps: `deployment.yml`, `service.yml` (LoadBalancer), `namespace.yml`, `configmap.yml`, `secret.yml`, `ingress.yml`.

### whanos.yml spec

When present at repo root with a `deployment` key, triggers Kubernetes deployment:
```yaml
deployment:
  replicas: 3          # default: 1
  resources:           # Kubernetes resource spec syntax
    limits:
      memory: "128M"
    requests:
      memory: "64M"
  ports:               # integer list, forwarded and externally accessible
    - 3000
```

## Commands

```bash
# Deploy full infrastructure
ansible-playbook -i ansible/inventories/host ansible/site.yml

# Build a single base image
docker build -t whanos-c - < images/c/Dockerfile.base
docker build -t whanos-java - < images/java/Dockerfile.base

# Build a standalone image (from app directory context)
docker build -t myapp -f images/c/Dockerfile.standalone .
```

## Key Constraints

- Base images MUST build without any app code/resources/dependencies available (they are templates)
- Images must use bash (`/bin/bash`) for all build instructions
- Compiled language images must strip source files from final image (only keep executables)
- A repo cannot match multiple language detection criteria simultaneously
- Jenkins must support private Git repositories (not just GitHub/GitLab)
- Kubernetes cluster requires at least 2 nodes
- Ports defined in `whanos.yml` must be accessible from outside the cluster
- Documentation goes in `docs/` directory
- Do NOT run Docker-in-Docker-in-Jenkins (Docker-in-Jenkins is fine)

## Example Apps (`app/`)

Sample Whanos-compatible applications for testing: `c-hello-world`, `java-hello-world`, `js-hello-world`, `python-hello-world`, `ts-hello-world`, `befunge-hello-world`. The `ts-hello-world` includes a `whanos.yml` demonstrating Kubernetes deployment config.
