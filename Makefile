.PHONY: install lint type test security migrate dev docker-build helm-lint helm-template helm-template-external helm-check helm-template-secrets

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
