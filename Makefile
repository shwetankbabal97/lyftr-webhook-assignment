# Run the app in the background (-d) and rebuild if code changed
up:
	docker compose up -d --build

# Stop the app and remove containers
down:
	docker compose down

# View logs (follow mode -f)
logs:
	docker compose logs -f api

# Run tests
test:
	docker compose exec api pytest