.PHONY: config-check migration-check image-scan sbom install lint type test security migrate dev demo-reset-schema demo-reset demo-check demo docker-build helm-lint helm-template helm-template-external helm-check helm-template-secrets

config-check:
	python -m ghostrecon.common.preflight --format text

migration-check:
	sh scripts/validate_migrations.sh

image-scan:
	trivy image --severity HIGH,CRITICAL --exit-code 1 --format json --output trivy-report.json ghostrecon:local

sbom:
	syft ghostrecon:local -o spdx-json=sbom.spdx.json -o cyclonedx-json=sbom.cyclonedx.json

install:
	python -m pip install --upgrade pip
	python -m pip install ".[dev]"

lint:
	ruff check .

type:
	mypy src

test:
	pytest

security:
	bandit -r src

migrate:
	alembic upgrade head

dev:
	docker compose up --build

demo-reset-schema:
	sh scripts/demo_reset.sh

demo-reset:
	sh scripts/demo_reset.sh

demo-check:
	sh scripts/demo_check.sh

demo: demo-reset
	docker compose up --build -d
	sh scripts/demo_check.sh

docker-build:
	docker build -t ghostrecon:local .

helm-lint:
	helm lint deploy/helm/ghostrecon -f deploy/helm/ghostrecon/tests/values-internal.yaml
	helm lint deploy/helm/ghostrecon -f deploy/helm/ghostrecon/tests/values-external.yaml

helm-template:
	helm template ghostrecon deploy/helm/ghostrecon -f deploy/helm/ghostrecon/tests/values-internal.yaml

helm-template-external:
	helm template ghostrecon deploy/helm/ghostrecon -f deploy/helm/ghostrecon/tests/values-external.yaml

helm-check:
	sh scripts/check_helm.sh

helm-template-secrets:
	helm secrets template ghostrecon deploy/helm/ghostrecon -f deploy/helm/ghostrecon/secrets.sops.yaml
