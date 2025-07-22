# SafeLinks
SafeLinks is a microservice-based platform for generating, resolving, and managing expiring access links. It's built with Flask, Docker, and Google Cloud Run, and is designed to be fast, scalable, and easy to integrate with other platforms.

## 🧠 What Problem Does It Solve?
Sometimes you want to give access to something, a file, a URL, a private page but only temporarily. Maybe just for a few hours. Maybe once. Maybe to one person.

SafeLinks handles this by generating secure expiring links that auto-expire based on time, usage, or both. No more manually deleting links. No more over-permissioned sharing.

## 🛠️ Architecture Overview
This system is split into three independent services, each deployed as a Docker container to Google Cloud Run:

### 1. creator
* Creates and stores expiring links.

* Accepts payload with original URL + expiration rules

* Generates unique shortlink ID

* Stores metadata securely in Firestore

* Returns the full public link to the client

### 2. resolver
* Resolves short links and handles expiration logic.

* Receives shortlink hit

* Validates against expiration rules (time or click count)

* Redirects to original URL or returns expired message

### 3. delete
* Manages manual deletions and automatic cleanup.

* Exposes an endpoint to explicitly delete links

* Supports scheduled Firestore cleanup of expired links

## ☁️ Deployment
All services are built as Docker images and deployed to Google Cloud Run with GCP's Artifact Registry and Firestore as the backend DB.

Each service includes:

* Dockerfile for containerization

* .env support for local development

* gcp-service-account.json for GCP auth

> You can run the services locally using docker run or deploy them using gcloud run deploy.

## 🔐 Tech Stack

Frontend: *React*

Backend: *Flask*

Database: *Firestore*

Cloud Platform: *Google Cloud Run*

Containerization: *Docker*

Authentication: *Service Account with scoped permissions*

## 🚀 Example Use Case
Let’s say you're sending someone a confidential document and want the link to expire in 24 hours or after a single click.

You hit the creator service with your document URL and expiration rules.

It gives you a shortlink and stores it in Firestore. The user clicks it → the resolver service checks if the link is valid and redirects.

Once expired, the link becomes useless.

Optionally, the delete service cleans it up in the background.