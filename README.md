## GCP Deployment Mario Sandbox

### Authentication

```commandline
export PROJECT_ID="df-gost-planner-sbx-57d9"
```
```commandline
gcloud auth login
```
```commandline
gcloud config set project $PROJECT_ID
```

### Back-End

#### 1. Build
```commandline
docker build -t europe-west1-docker.pkg.dev/df-gost-planner-sbx-57d9/gostplanner-repo/gostplanner-backend:latest .
```
#### 2. Push the Image to Artifact Registry
```commandline
docker push europe-west1-docker.pkg.dev/df-gost-planner-sbx-57d9/gostplanner-repo/gostplanner-backend:latest
```
#### 3. Deploy to Cloud Run (Ensure all-traffic is set)
```commandline
gcloud run deploy gostplanner-backend \
  --image europe-west1-docker.pkg.dev/df-gost-planner-sbx-57d9/gostplanner-repo/gostplanner-backend:latest \
  --region europe-west1 \
  --env-vars-file env.yaml \
  --service-account gcp-df-gostplanner-sbx-backend@df-gost-planner-sbx-57d9.iam.gserviceaccount.com \
  --vpc-connector projects/df-network-dta-51a0/locations/europe-west1/connectors/sva-df-sharedvpc-dta \
  --vpc-egress all-traffic
```

### Front-End

#### 1. Set environmental Variables
```commandline
export PROJECT_ID="df-gost-planner-sbx-57d9"
export REGION="europe-west1"
export REPO_NAME="gostplanner-repo"
export IMAGE_NAME="gostplanner-frontend"
export BACKEND_URL="https://gostplannersbx.ddns.net"
export IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}:latest"
```
#### 2. Build (Injecting the Backend URL)
```commandline
docker build --build-arg VITE_API_URL=$BACKEND_URL -t $IMAGE_URL .
```
#### 3. Push the Image to Artifact Registry
```commandline
docker push $IMAGE_URL
```
#### 4. Deploy to Cloud Run
```commandline
gcloud run deploy $IMAGE_NAME \
  --image $IMAGE_URL \
  --region $REGION \
  --allow-unauthenticated
```

### Luigi

#### 1. Build
```commandline
docker build -t europe-west1-docker.pkg.dev/df-gost-planner-sbx-57d9/gostplanner-repo/sherlock-worker:latest .
```

#### 2. Push the Image to Artifact Registry
```commandline
docker push europe-west1-docker.pkg.dev/df-gost-planner-sbx-57d9/gostplanner-repo/sherlock-worker:latest
```

#### 3. Deploy to Cloud Run
```commandline
gcloud run deploy sherlock-worker \
  --image europe-west1-docker.pkg.dev/df-gost-planner-sbx-57d9/gostplanner-repo/sherlock-worker:latest \
  --region europe-west1 \
  --no-allow-unauthenticated \
  --service-account gcp-df-gostplanner-sbx-backend@df-gost-planner-sbx-57d9.iam.gserviceaccount.com \
  --vpc-connector projects/df-network-dta-51a0/locations/europe-west1/connectors/sva-df-sharedvpc-dta \
  --vpc-egress all-traffic \
  --set-env-vars GCP_PROJECT_ID=df-gost-planner-sbx-57d9,LOCATION=europe-west1,DB_INSTANCE_NAME=gcp-df-gostplanner-sbx-db,POSTGRES_DB=gostplanner-sbx-db,IAM_SA_EMAIL=gcp-df-gostplanner-sbx-backend@df-gost-planner-sbx-57d9.iam.gserviceaccount.com,INTAKE_BUCKET_NAME=gcp-df-gostplanner-sbx-intake-artifacts-bucket,GEMINI_KEY_NAME=gcp-luigi-key,MAIN_BACKEND_URL=https://gostplannersbx.ddns.net,IAP_CLIENT_ID=114457953986-04hqpgf4i4ellvv51q84at2l26argjie.apps.googleusercontent.com
```

#### 4. Create the pub/sub Subscriptions
```commandline
gcloud pubsub subscriptions create sherlock-worker-push-subscription \
    --topic=gost_planner_trigger_ai_intake \
    --push-endpoint=https://sherlock-worker-114457953986.europe-west1.run.app \
    --push-auth-service-account=gcp-df-gostplanner-sbx-backend@df-gost-planner-sbx-57d9.iam.gserviceaccount.com \
    --ack-deadline=600
```

#### 5. Authorize the Backed SA to invoke Luigi
```commandline
gcloud run services add-iam-policy-binding sherlock-worker \
  --region=europe-west1 \
  --member="serviceAccount:gcp-df-gostplanner-sbx-backend@df-gost-planner-sbx-57d9.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```