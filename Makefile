.PHONY: build run run-fast fix-shopmy

build:
	docker build -t url-unfurler .

run:
	time docker run --rm -v "$(PWD)":/app url-unfurler

run-fast:
	docker run --rm -v "$(PWD)":/app -e AGGRESSIVE_MODE=false url-unfurler

fix-shopmy:
	docker run --rm -v "$(PWD)":/app --entrypoint python3 url-unfurler fix_shopmy_urls.py

