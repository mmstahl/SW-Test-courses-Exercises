# Docker Workflow

This repository uses Docker Compose to build Windows executables with Wine and serve the generated student workspace with JupyterLab.

## Requirements

- Docker Desktop or Docker Engine with Compose
- Docker Hub access only when pushing images

## Build Everything

From the repository root:

```bash
BUILD_TARGET=all docker compose run --build --rm sandbox
docker compose build jupyter
docker compose up -d jupyter
```

The sandbox recreates `student-workspace/` and generates all supported executables. Jupyter serves that folder at `/home/jovyan/work`.

Open JupyterLab at:

```text
http://localhost:8888/lab
```

## Build One Target

The supported target names are:

- `transform_obj`
- `check_age.v99`
- `check_age.v100`
- `triage_rules`
- `trace_it`
- `get_a_room`

Example:

```bash
BUILD_TARGET=triage_rules docker compose run --build --rm sandbox
docker compose up -d jupyter
```

This clears the existing `student-workspace/` and creates only:

```text
student-workspace/05.1 Decision tables activity/triage_rules.exe
```

After the sandbox image has been rebuilt once, `--build` can usually be omitted:

```bash
BUILD_TARGET=triage_rules docker compose run --rm sandbox
```

## Convenience Scripts

Linux or macOS:

```bash
./scripts/build_students.sh
```

PowerShell:

```powershell
./scripts/build_students.ps1
```

A target can be selected through the environment:

```bash
BUILD_TARGET=trace_it ./scripts/build_students.sh
```

```powershell
$env:BUILD_TARGET = "trace_it"
./scripts/build_students.ps1
```

## Image Names

The Jupyter image is built locally as:

```text
students:latest
```

The Wine build image is:

```text
wine-pyinstaller:py3.9.13
```

## Push the Student Image

Build the complete workspace and image, then tag and push it:

```bash
BUILD_TARGET=all docker compose run --build --rm sandbox
docker compose build jupyter
docker tag students:latest ephicohen/sw-test-courses-exercises-26:01
docker push ephicohen/sw-test-courses-exercises-26:01
```

Pull it on another host:

```bash
docker pull ephicohen/sw-test-courses-exercises-26:01
docker run --rm -p 8888:8888 ephicohen/sw-test-courses-exercises-26:01
```

Open `http://localhost:8888/lab`.

## Stop and Clean Up

Stop the Jupyter service:

```bash
docker compose down
```

Remove the generated student workspace manually:

```bash
rm -rf student-workspace/*
```

The next sandbox build recreates it automatically.
