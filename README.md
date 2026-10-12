# Jenkins CI/CD Lab: Loan Quote API

A small Flask API that calculates the monthly payment on a vehicle loan, together with a full Jenkins pipeline:

```
Checkout → Secret scan → Install → [Lint | Unit tests | SAST] → Build image → Image scan
        → Deploy DEV → Smoke test → Manual approval → Deploy PROD (auto-rollback on failure)
```

| Path | What it is |
|---|---|
| `app/main.py` | Flask API: `GET /health`, `POST /api/v1/quote` |
| `tests/` | pytest unit and API tests (coverage gate set to 80%) |
| `Dockerfile` | Multi-stage build that runs as a non-root user and has a healthcheck |
| `Jenkinsfile` | Declarative pipeline (the main thing to learn here) |
| `jenkins/` | Custom Jenkins image with Python, Docker CLI, gitleaks, Trivy and plugins |
| `docker-compose.yml` | Starts Jenkins on `localhost:8080` |

---

## Prerequisites
- A Linux machine or VM (Ubuntu 22.04/24.04 works well) with **Docker** and **Docker Compose**. WSL2 also works.
- A **personal** GitHub account. Use a personal account for practice, not a company organisation.
- Roughly 4 GB RAM free.

## Part 1: Run the app locally (15 min)
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q --cov=app            # 9 tests should pass
flake8 app tests
python -m app.main             # then in another shell:
curl -X POST localhost:5000/api/v1/quote -H 'Content-Type: application/json' \
     -d '{"principal":1000000,"annual_rate":12,"months":12}'
```

## Part 2: Push to GitHub
```bash
git init && git add . && git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<you>/jenkins-loan-api.git
git push -u origin main
```

## Part 3: Start Jenkins (20 min)
```bash
DOCKER_GID=$(getent group docker | cut -d: -f3) docker compose up -d --build
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```
1. Open http://localhost:8080 and paste the password.
2. Choose **Install suggested plugins**. The ones the pipeline needs are already baked in.
3. Create your admin user. Don't keep using the initial password.

## Part 4: Create the pipeline job
1. Go to **New Item**, enter `loan-api`, choose **Pipeline**, then **OK**.
2. Under **Pipeline**, set the definition to **Pipeline script from SCM**. Set SCM to Git, enter your repo URL and set the branch to `*/main`.
   - If the repo is private, add a GitHub **fine-grained Personal Access Token** under *Manage Jenkins → Credentials*, scoped to that single repo with read-only contents.
3. Set the script path to `Jenkinsfile` and save.
4. Click **Build Now** and watch the Stage View.
5. When the build pauses at **Approve PROD**, click **Deploy**.

Check the results:
- DEV: http://localhost:8081/health
- PROD: http://localhost:8090/health (the `version` field shows the build tag)
- Test results: open the build page and look at **Test Result**. Scan reports are under **Artifacts**.

---

## Part 5: Exercises (where most of the learning happens)
Do these one at a time. Commit each change, push it, and watch what the pipeline does.

**Break things on purpose**
1. Change an expected value in a test and push. The *Unit tests* stage should fail and nothing should deploy.
2. Add an unused import. The *Lint* stage should fail.
3. Add the line `AWS_SECRET_ACCESS_KEY = "AKIA..."` (use a fake value) and push. *Secret scan* should catch it. Then think about why deleting the line in the next commit doesn't fully fix the problem, because the secret is still in git history.
4. Change the Dockerfile base image to an old one such as `python:3.8-slim`. *Image scan* should fail on CVEs.
5. Make `/health` return HTTP 500 only in PROD (hint: use an env var). Confirm the automatic rollback runs.

**Level up the pipeline**

6. **Triggers:** add `triggers { pollSCM('H/5 * * * *') }`, or set up a GitHub webhook through an ngrok/Cloudflare tunnel.
7. **Multibranch:** convert the job to a *Multibranch Pipeline*. Wrap the deploy stages in `when { branch 'main' }` so feature branches only run CI.
8. **Registry:** push the image to Docker Hub or GHCR. Store the token as a Jenkins credential and use `withCredentials`, and never `echo` it.
9. **Agents:** add a separate Jenkins agent (an SSH node or a Docker cloud agent) and stop running builds on the controller. Set *controller executors* to 0.
10. **Shared library:** move `deploy()` and `smokeTest()` into a Jenkins Shared Library repo and call it with `@Library('my-lib') _`.
11. **Notifications:** send a message to Slack, Teams or email on failure in the `post { failure { } }` block.
12. **Jenkins as code:** use the *Configuration as Code (JCasC)* plugin to define the admin user, credentials and job in YAML, so `docker compose up` rebuilds the whole server from nothing.
13. **Deploy to Kubernetes:** run k3s or kind in your home lab and replace `docker run` with `kubectl apply` or Helm.

---

## Security notes (read these)
- **The Docker socket mount is root-equivalent.** Anyone who can run a pipeline step can take over the host. That's acceptable for a throwaway lab VM. In real setups, use dedicated build agents, rootless Docker, Kaniko or BuildKit, or ephemeral Kubernetes pod agents.
- Jenkins and the app are bound to `127.0.0.1`. Don't expose port 8080 to the internet. If you need remote access, put it behind a VPN or reverse proxy with TLS and SSO.
- Keep Jenkins and its plugins updated, because plugins are its biggest attack surface. Install only what you need.
- Pin tool versions, and verify checksums where you can (gitleaks and Trivy are pinned in `jenkins/Dockerfile`). Supply-chain attacks on CI tooling are common.
- Use **Manage Jenkins → Security**: turn on matrix-based authorisation and don't give anonymous users read access.
- Practise on personal infrastructure. Bring patterns to work through your organisation's approved change process.

## Teardown
```bash
docker rm -f loan-api-dev loan-api-prod
docker compose down -v      # -v also deletes Jenkins data
```

## Troubleshooting
| Symptom | Fix |
|---|---|
| `permission denied ... docker.sock` | Restart with the `DOCKER_GID=...` prefix so the group matches the host's docker group |
| `docker: Error ... port is already allocated` | Something else is using 8081 or 8090. Change the port in `Jenkinsfile` |
| Image scan fails on a fresh build | Rebuild with `--pull` so you get the latest patched base image, or move to a newer base |
| Building on an ARM machine (Apple Silicon, Raspberry Pi) | In `jenkins/Dockerfile`, change `linux_x64` to `linux_arm64` |
