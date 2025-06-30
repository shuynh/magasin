.PHONY: build run

build:
	docker build -t url-unfurler .

run:
	docker run --rm -v "$(PWD)":/app url-unfurler

