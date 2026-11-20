.PHONY: setup up down reset logs ps seed psql topics

setup:
	@test -f .env || cp .env.example .env
	@test -f config/thresholds.yaml || cp config/thresholds.example.yaml config/thresholds.yaml
	@test -f config/rules.yaml || cp config/rules.example.yaml config/rules.yaml

up: setup
	docker compose up -d

down:
	docker compose down

# Removes volumes so the schema is re-applied from scratch
reset:
	docker compose down -v

logs:
	docker compose logs -f

ps:
	docker compose ps

seed:
	docker compose run --rm --build simulator history --reset

psql:
	docker compose exec postgres sh -c 'psql -U $$POSTGRES_USER -d $$POSTGRES_DB'

topics:
	docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
