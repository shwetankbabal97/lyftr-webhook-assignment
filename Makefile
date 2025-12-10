# Run the app in the background (-d) and rebuild if code changed
up:
	docker compose up -d --build

# Stop the app and remove containers and volumes
down:
	docker compose down -v

# View logs (follow mode -f)
logs:
	docker compose logs -f api

# Run tests inside container
test:
	docker compose exec api pytest -v

# Run tests locally (requires dependencies installed)
test-local:
	WEBHOOK_SECRET=testsecret DATABASE_URL=sqlite:///./test.db pytest -v