-include .env
POSTGRES_HOST ?= localhost
POSTGRES_PORT ?= 5432
export PGPASSWORD = $(POSTGRES_PASSWORD)
PSQL = psql -h $(POSTGRES_HOST) -p $(POSTGRES_PORT) -U $(POSTGRES_USER) -v ON_ERROR_STOP=1

.PHONY: setup db up down logs ps seed train live attack psql topics

setup:
	@test -f .env || cp .env.example .env
	@test -f config/thresholds.yaml || cp config/thresholds.example.yaml config/thresholds.yaml
	@test -f config/rules.yaml || cp config/rules.example.yaml config/rules.yaml

# Creates the database if missing and (re)applies the schema
db: setup
	@$(PSQL) -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$(POSTGRES_DB)'" | grep -q 1 \
		|| $(PSQL) -d postgres -c "CREATE DATABASE $(POSTGRES_DB)"
	@for f in infra/postgres/init/*.sql; do $(PSQL) -d $(POSTGRES_DB) -q -f $$f || exit 1; done

up: setup
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

seed:
	docker compose run --rm --build simulator history --reset

train:
	docker compose run --rm --build trainer

live:
	docker compose run --rm --build simulator live $(ARGS)

attack:
	docker compose run --rm --build simulator attack $(TYPE) $(ARGS)

psql:
	$(PSQL) -d $(POSTGRES_DB)

topics:
	docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
