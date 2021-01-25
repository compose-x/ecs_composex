ARG ARCH=
ARG SRC_TAG=3.7.20210113
ARG BASE_IMAGE=public.ecr.aws/i9v7p2w3/python:${SRC_TAG}${ARCH}
ARG LAMBDA_IMAGE=public.ecr.aws/lambda/python:latest
FROM $BASE_IMAGE as builder

WORKDIR /opt
COPY ecs_composex       /opt/ecs_composex
COPY setup.py requirements.txt MANIFEST.in README.rst LICENSE /opt/
RUN python -m venv venv ; source venv/bin/activate ; pip install wheel;  python setup.py sdist bdist_wheel; ls -l dist/

FROM $BASE_IMAGE
COPY --from=builder /opt/dist/ecs_composex-*.whl /opt/
WORKDIR /opt
RUN pip install pip -U --no-cache-dir && pip install wheel --no-cache-dir && pip install *.whl --no-cache-dir
WORKDIR /tmp
ENTRYPOINT ["ecs-composex"]
