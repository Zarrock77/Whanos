# Whanos

Whanos is a DevOps infrastructure that automatically detects, containerizes, and deploys applications to a Kubernetes cluster on every Git push. It supports **C**, **Java**, **JavaScript**, **Python**, and **Befunge**.

**Pipeline flow:** `Git push → Jenkins detects change → auto-detect language → containerize → push to registry → deploy to Kubernetes`

![CI](https://github.com/Zarrock77/Whanos/actions/workflows/ci.yml/badge.svg)

## Table of Contents

- [How It Works](#how-it-works)
- [Language Detection](#language-detection)
- [Docker Images](#docker-images)
- [Deploying to Kubernetes](#deploying-to-kubernetes)
- [Infrastructure Setup](#infrastructure-setup)
- [Jenkins Configuration](#jenkins-configuration)
- [Project Structure](#project-structure)
- [CI Pipeline](#ci-pipeline)
- [Example Applications](#example-applications)

## How It Works

1. A developer pushes code to a Git repository
2. Jenkins polls the repository and detects the change
3. The pipeline identifies the language based on specific files at the repo root
4. If the repo contains a custom `Dockerfile`, it is used directly
5. Otherwise, a **standalone Dockerfile** is selected based on the detected language
6. The image is built and pushed to the Docker registry
7. If a `whanos.yml` file is present at the repo root, the app is deployed to Kubernetes

## Language Detection

Detection is **mutually exclusive** — a repository must match exactly one language:

| Language   | Detection File    | Execution Command  |
|------------|-------------------|--------------------|
| C          | `Makefile`        | `./compiled-app`   |
| Java       | `app/pom.xml`     | `java -jar app.jar`|
| JavaScript | `package.json`    | `node .`           |
| Python     | `requirements.txt`| `python -m app`    |
| Befunge    | `app/main.bf`     | `befunge93 main.bf`|

Application source code must live in the `app/` directory of Whanos-compatible repositories.

## Docker Images

Each language has two Docker image types in `images/<language>/`:

### Base Images (`Dockerfile.base`)

Template images that set up the build environment without any application code. They use `ONBUILD` directives to defer copying and building the app to when a child image is built from them.

```bash
# Build a base image (no app code needed)
docker build -t whanos-c - < images/c/Dockerfile.base
docker build -t whanos-java - < images/java/Dockerfile.base
```

Base images are intended as `FROM` targets when apps provide their own Dockerfile:
```dockerfile
FROM whanos-c
# ONBUILD triggers copy source and compile automatically
```

### Standalone Images (`Dockerfile.standalone`)

Complete, self-contained images used when apps **do not** provide their own Dockerfile. The Jenkins pipeline copies the appropriate standalone Dockerfile into the project and builds it.

```bash
# Build a standalone image with an example app
docker build -f images/c/Dockerfile.standalone -t my-c-app app/c-hello-world/
```

### Key Constraints

- Base images must build without any app code available
- All images use `/bin/bash` as their shell
- Compiled language images (C, Java) strip source files from the final image

## Deploying to Kubernetes

To trigger automatic Kubernetes deployment, add a `whanos.yml` file at the root of your repository:

```yaml
deployment:
  replicas: 3
  resources:
    limits:
      memory: "128M"
    requests:
      memory: "64M"
  ports:
    - 3000
```

| Field      | Description                                      | Default |
|------------|--------------------------------------------------|---------|
| `replicas` | Number of pod replicas                           | 1       |
| `resources`| Kubernetes resource spec (limits/requests)       | —       |
| `ports`    | List of ports to expose outside the cluster      | —       |

Kubernetes manifest templates are in the `kubernetes/` directory.

## Infrastructure Setup

The entire infrastructure is provisioned with **Ansible**:

```bash
ansible-playbook -i ansible/inventories/host ansible/site.yml
```

Ansible executes four roles in order:

| Order | Role         | What it does                                                  |
|-------|--------------|---------------------------------------------------------------|
| 1     | `docker`     | Installs the Docker runtime                                  |
| 2     | `jenkins`    | Installs Java + Jenkins, deploys JCasC config, installs plugins (job-dsl, git, role-strategy, configuration-as-code) |
| 3     | `kubernetes` | Installs kubeadm/kubectl/kubelet, initializes the cluster with Calico CNI |
| 4     | `whanos`     | Builds all base Docker images for every supported language    |

### Requirements

- At least 2 nodes for the Kubernetes cluster
- SSH access configured in `ansible/inventories/host`

## Jenkins Configuration

Jenkins uses **Configuration as Code (JCasC)** and **Job DSL** for fully declarative setup.

### Jobs

- **Whanos base images/** — One build job per language + a "Build all base images" trigger
- **Projects/** — Dynamically created jobs for linked repositories
- **link-project** — Root job that accepts a Git URL and project name, creates a polling job that auto-builds and deploys on every commit

### Linking a Project

Run the `link-project` Jenkins job with:
- `GIT_REPOSITORY_URL` — the Git clone URL
- `PROJECT_NAME` — a name for the project

Jenkins will create a new job that polls the repository every minute and triggers the full build/deploy pipeline on changes.

### Admin Users

A single `admin` account is created. Sign-up is disabled. The password is set via the `JENKINS_ADMIN_PASSWORD` environment variable.

## Project Structure

```
whanos/
├── .github/workflows/ci.yml    # GitHub Actions CI pipeline
├── ansible/
│   ├── inventories/host         # Ansible inventory
│   ├── site.yml                 # Main playbook
│   └── roles/
│       ├── docker/              # Docker installation
│       ├── jenkins/             # Jenkins setup + plugins + JCasC
│       ├── kubernetes/          # K8s cluster initialization
│       └── whanos/              # Base image builds
├── jenkins/
│   ├── config.yml               # JCasC configuration
│   └── jobs.groovy              # Job DSL definitions
├── kubernetes/
│   ├── deployment.yml           # Deployment template
│   ├── service.yml              # LoadBalancer service template
│   ├── namespace.yml            # Namespace template
│   ├── configmap.yml            # ConfigMap template
│   ├── secret.yml               # Secret template
│   └── ingress.yml              # Ingress template
├── images/
│   └── <language>/
│       ├── Dockerfile.base       # Base image (ONBUILD, no app code)
│       └── Dockerfile.standalone # Standalone image (complete)
└── app/                          # Example Whanos-compatible apps
    ├── c-hello-world/
    ├── java-hello-world/
    ├── js-hello-world/
    ├── python-hello-world/
    ├── befunge-hello-world/
    └── ts-hello-world/           # Includes whanos.yml + custom Dockerfile
```

## CI Pipeline

The GitHub Actions workflow validates the entire project on every push:

| Job                     | What it tests                                              |
|-------------------------|------------------------------------------------------------|
| **Base images** (x5)   | Each base Dockerfile builds without app code               |
| **Standalone** (x5)    | Build with example apps + verify container output          |
| **Ansible**             | `ansible-playbook --syntax-check` + `ansible-lint`         |
| **Kubernetes**          | Manifest validation with `kubeconform`                     |
| **Jenkins**             | JCasC YAML validation + Groovy syntax check                |

## Example Applications

| App                  | Language   | Type   | Output                     |
|----------------------|------------|--------|----------------------------|
| `c-hello-world`      | C          | CLI    | `Hello world!`             |
| `java-hello-world`   | Java       | CLI    | `Hello World!`             |
| `js-hello-world`     | JavaScript | Server | Express on port 3000       |
| `python-hello-world` | Python     | Server | Flask on port 8080         |
| `befunge-hello-world`| Befunge    | CLI    | `Hello World!`             |
| `ts-hello-world`     | TypeScript | Server | Express on port 3000 (custom Dockerfile + `whanos.yml`) |

The `ts-hello-world` app demonstrates the full pipeline with a custom Dockerfile and Kubernetes deployment configuration.

## License

[MIT](LICENSE)
