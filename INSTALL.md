# Installation Guide for ecs_composex

## Standard Installation

For most Python versions (3.9-3.11), installation is straightforward:

```bash
pip install ecs-composex
```

## Python 3.12+ Installation

### Issue Background

The `flatdict` package (version 4.0.1), which is a transitive dependency through `compose-x-common`, has a build issue with Python 3.12+. The package's `setup.py` imports `pkg_resources`, which is deprecated and no longer available by default in Python 3.12's setuptools.

### Solution 1: Using the Provided Pre-built Wheel (Recommended)

If you've cloned this repository, use the pre-built wheel provided in the `vendor-wheels/` directory:

```bash
git clone https://github.com/compose-x/ecs_composex.git
cd ecs_composex
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools

# Install flatdict from the provided wheel
pip install vendor-wheels/flatdict-4.0.1-py3-none-any.whl

# Now install ecs-composex
pip install .
```

### Solution 2: Install from PyPI

When installing from PyPI (not from source), you can install setuptools first:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools
pip install ecs-composex
```

**Note**: If you still encounter issues, try installing flatdict separately first:

```bash
# Build flatdict from source with setuptools available
pip install setuptools>=65.5.0
pip download --no-deps --no-binary=:all: flatdict==4.0.1
tar -xzf flatdict-4.0.1.tar.gz
cd flatdict-4.0.1

# Patch the setup.py to remove pkg_resources requirement
cat > setup.py << 'EOF'
import setuptools
setuptools.setup()
EOF

# Create proper build configuration
cat > pyproject.toml << 'EOF'
[build-system]
requires = ["setuptools>=39.2", "wheel"]
build-backend = "setuptools.build_meta"
EOF

# Build and install
pip install .
cd ..

# Now install ecs-composex
pip install ecs-composex
```

### Solution 3: Using Poetry

If you're using Poetry for dependency management:

```bash
poetry install
```

Poetry should handle the dependency resolution automatically with the setuptools dependency we've added.

## Verification

After installation, verify that ecs-composex is installed correctly:

```bash
ecs-compose-x --version
```

## Troubleshooting

If you encounter the error:
```
ModuleNotFoundError: No module named 'pkg_resources'
```

This confirms the flatdict build issue. Use Solution 1 or Solution 2 above to resolve it.

## Development Installation

For development purposes:

```bash
git clone https://github.com/compose-x/ecs_composex.git
cd ecs_composex
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools

# Install flatdict from provided wheel
pip install vendor-wheels/flatdict-4.0.1-py3-none-any.whl

# Install in development mode
pip install -e .
```
