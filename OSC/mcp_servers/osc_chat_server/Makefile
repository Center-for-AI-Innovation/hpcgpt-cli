REL := $(shell cat VERSION.txt)
build:
	podman build \
		--platform linux/amd64 \
		-t docker-registry.osc.edu/kubernetes/hpcgpt/oscchat-mcp:${REL} \
		.
push:
	podman push docker-registry.osc.edu/kubernetes/hpcgpt/oscchat-mcp:${REL}
