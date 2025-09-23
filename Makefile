.PHONY: build run fix-shopmy

build:
	docker build -t url-unfurler .

run:
	docker run --rm -v "$(PWD)":/app url-unfurler

fix-shopmy:
	docker run --rm -v "$(PWD)":/app --entrypoint python3 url-unfurler fix_shopmy_urls.py

