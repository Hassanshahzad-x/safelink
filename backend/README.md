# CREATOR SERVICE

## LOCAL

Docker build
```
docker build -t {{CREATOR_IMAGE_NAME}} -f {{CREATOR_DOCKERFILE_PATH}} .
```

Run container

```
docker run -d \
--name {{CREATOR_CONTAINER_NAME}} \
--env-file {{LOCAL_ENV_FILE_PATH}} \
-v {{LOCAL_GCP_KEY_PATH}}:/app/gcp-service-account.json \
-e GOOGLE_APPLICATION_CREDENTIALS=/app/gcp-service-account.json \
-p {{LOCAL_PORT}}:5000 {{CREATOR_IMAGE_NAME}}
```
## CLOUD

Build Docker image

```
docker build -t {{GCP_DOCKER_IMAGE_PATH}} -f {{CREATOR_DOCKERFILE_PATH}} .
```

Push using Docker Buildx
```
cd {{CREATOR_SERVICE_DIRECTORY}}

docker buildx build \
--platform linux/amd64 \
--tag {{GCP_DOCKER_IMAGE_PATH}} \
--file Dockerfile \
.. \
--push
```

Deploy to GCP

```
gcloud run deploy {{CREATOR_SERVICE_NAME}} \
--image={{GCP_DOCKER_IMAGE_PATH}} \
--platform=managed \
--region={{GCP_REGION}} \
--allow-unauthenticated \
--set-env-vars=RESOLVER_SERVICE_URL={{RESOLVER_PUBLIC_URL}}
```

# RESOLVER SERVICE

## LOCAL

Docker build

```
docker build -t {{RESOLVER_IMAGE_NAME}} -f {{RESOLVER_DOCKERFILE_PATH}} .
```

Run container

```
docker run -d \
--name {{RESOLVER_CONTAINER_NAME}} \
-v {{LOCAL_GCP_KEY_PATH}}:/app/gcp-service-account.json \
-e GOOGLE_APPLICATION_CREDENTIALS=/app/gcp-service-account.json \
-p {{LOCAL_PORT}}:5000 {{RESOLVER_IMAGE_NAME}}
```

## CLOUD

Build Docker image

```
docker build -t {{GCP_DOCKER_IMAGE_PATH}} -f {{RESOLVER_DOCKERFILE_PATH}} .
```

Push using Docker Buildx

```
cd {{RESOLVER_SERVICE_DIRECTORY}}

docker buildx build \
--platform linux/amd64 \
--tag {{GCP_DOCKER_IMAGE_PATH}} \
--file Dockerfile \
.. \
--push
```

Deploy to GCP

```
gcloud run deploy {{RESOLVER_SERVICE_NAME}} \
--image={{GCP_DOCKER_IMAGE_PATH}} \
--platform=managed \
--region={{GCP_REGION}} \
--allow-unauthenticated
```