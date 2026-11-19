mkdir -p dextop-build/dextop && cd dextop-build

cat > README.md <<'EOF'
# DeXtop

Alternative open-source à Samsung DeX, basée sur scrcpy.

## Statut
🚧 En construction — v0.1.0

## Installation
Voir la page Releases (à venir).
EOF

cat > LICENSE <<'EOF'
Apache License 2.0
Copyright (c) 2026 mamanbako

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0
EOF

cat > pyproject.toml <<'EOF'
[project]
name = "dextop"
version = "0.1.0"
description = "Alternative open-source à Samsung DeX basée sur scrcpy"
requires-python = ">=3.10"
dependencies = ["customtkinter>=5.2"]

[project.scripts]
dextop-gui = "dextop.gui:run"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
EOF

cat > .gitignore <<'EOF'
__pycache__/
*.pyc
build/
dist/
bin/
.venv/
EOF

cat > dextop/__init__.py <<'EOF'
"""DeXtop — Alternative open-source à Samsung DeX basée sur scrcpy."""
__version__ = "0.1.0"
EOF

ls -R