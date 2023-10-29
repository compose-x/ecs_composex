ARG ARCH=
ARG PY_VERSION=3.10-slim
ARG BASE_IMAGE=public.ecr.aws/docker/library/python:$PY_VERSION
ARG LAMBDA_IMAGE=public.ecr.aws/lambda/python:latest

FROM $BASE_IMAGE as builder

WORKDIR /opt
RUN python -m pip install pip -U
RUN pip install poetry
COPY ecs_composex       /opt/ecs_composex
COPY pyproject.toml poetry.lock MANIFEST.in README.rst LICENSE /opt/
RUN poetry build

FROM $BASE_IMAGE
COPY --from=builder /opt/dist/ecs_composex-*.whl /opt/
WORKDIR /opt
RUN pip install pip -U --no-cache-dir && pip install wheel --no-cache-dir && pip install *.whl --no-cache-dir;\
    pip --no-cache-dir install ecs-composex[ecrscan]
WORKDIR /tmp
ENTRYPOINT ["ecs-compose-x"]
