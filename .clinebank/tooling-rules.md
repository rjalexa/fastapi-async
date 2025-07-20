# LLM Project Development Rules

## Container-First Development

### Rule 1: Always Use Containers
- **MANDATORY**: Launch all project artifacts as containers, never as local processes
- All applications must run in containerized environments
- No direct execution of local binaries or scripts outside of containers

### Rule 2: Docker Compose Command
- **MANDATORY**: Use `docker compose` (new syntax) for all container orchestration
- **FORBIDDEN**: Never use the deprecated `docker-compose` command (old syntax with hyphen)
- All compose operations must use the modern Docker CLI integrated command

## Frontend Development

### Rule 3: Frontend Container Deployment
- **MANDATORY**: Launch frontend applications by rebuilding their Docker image and launching with `docker compose`
- **FORBIDDEN**: Never use `pnpm run` or any local package manager commands to start frontend applications
- Frontend must always be containerized and orchestrated through Docker Compose

### Rule 4: React Package Management
- **MANDATORY**: For React projects, use `pnpm` as the package manager
- **FORBIDDEN**: Never use `npm` for React project dependency management
- All React dependencies must be managed through pnpm

### Rule 5: Frontend Pre-Build Validation
- **MANDATORY**: Before you try to build a react/frontend container run a pnpm lint and fix any errors
- Code quality must be verified before containerization
- All linting errors must be resolved prior to Docker build process

### Rule 6: Frontend Container Build and Test Process
- **MANDATORY**: To build and test a new version of a frontend container always use the `docker compose down FRONTENDNAME; docker compose up -d FRONTENDNAME --build`
- This ensures clean shutdown of existing containers before rebuilding
- Forces fresh build of the frontend container image
- Launches in detached mode for testing

## Python Development

### Rule 7: Python Package Management with Astral UV
- **MANDATORY**: Manage all Python packages using Astral UV with `pyproject.toml`
- **MANDATORY**: Use `uv sync` for dependency synchronization
- **FORBIDDEN**: Never use `pip` for package installation or management
- All Python dependencies must be declared in `pyproject.toml` and managed through UV

## Summary

These rules ensure:
- Consistent containerized development environment
- Modern Docker tooling usage
- Proper frontend containerization
- Code quality validation before containerization
- Standardized container rebuild and testing procedures
- Standardized package management per technology stack
- Reproducible development and deployment workflows

**Non-compliance with these rules is not acceptable and must be corrected immediately.**