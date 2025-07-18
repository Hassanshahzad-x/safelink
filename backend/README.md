# CREATOR SERVICE

## LOCAL

Docker build

```
docker build -t safelink-creator -f creator/Dockerfile .
```

Container run

```
docker run -d \
--name safelink-creator \
--env-file /Users/hassanshahzad/Desktop/Projects/safelinks/backend/.env \
-v /Users/hassanshahzad/Desktop/Projects/safelinks/backend/gcp-service-account.json:/app/gcp-service-account.json \
-e GOOGLE_APPLICATION_CREDENTIALS=/app/gcp-service-account.json \
-p 5002:5000 safelink-creator
```

## CLOUD

Docker build

```
docker build -t asia-south1-docker.pkg.dev/safelink-466211/safelinks-repo/safelink-creator -f creator/Dockerfile .
```

Docker Push to GCP

```
cd backend/creator

docker buildx build \
--platform linux/amd64 \
--tag asia-south1-docker.pkg.dev/safelink-466211/safelinks-repo/safelink-creator \
--file Dockerfile \
.. \
--push
```

Container Push to GCP
```
gcloud run deploy safelink-creator \
--image=asia-south1-docker.pkg.dev/safelink-466211/safelinks-repo/safelink-creator \
--platform=managed \
--region=asia-south1 \
--allow-unauthenticated \
--set-env-vars=BACKEND_BASE_URL=https://safelink-resolver-568539115852.asia-south1.run.app
```

# RESOLVER SERVICE

## LOCAL

Docker build

```
docker build -t safelink-resolver -f resolver/Dockerfile .
```

Container run

```
docker run -d \
--name safelink-resolver \
-v /Users/hassanshahzad/Desktop/Projects/safelinks/backend/gcp-service-account.json:/app/gcp-service-account.json \
-e GOOGLE_APPLICATION_CREDENTIALS=/app/gcp-service-account.json \
-p 5003:5000 safelink-resolver
```

## CLOUD

Docker build

```
docker build -t asia-south1-docker.pkg.dev/safelink-466211/safelinks-repo/safelink-resolver -f resolver/Dockerfile .
```

Docker Push to GCP

```
cd backend/resolver

docker buildx build \
--platform linux/amd64 \
--tag asia-south1-docker.pkg.dev/safelink-466211/safelinks-repo/safelink-resolver \
--file Dockerfile \
.. \
--push
```

Container Push to GCP
```
gcloud run deploy safelink-resolver \
--image=asia-south1-docker.pkg.dev/safelink-466211/safelinks-repo/safelink-resolver \
--platform=managed \
--region=asia-south1 \
--allow-unauthenticated  
```
