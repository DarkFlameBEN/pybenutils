# pybenutils
PyBEN Utilities repo

### Deployment
- Install deployment requirements
  - > python -m pip install deploy_requirements.txt -U
- Test the package
  - > pytest .
  - > pytest . --pep8
- Build the package
  - > python setup.py sdist bdist_wheel
- Deploy to repo (testpypi)
  - > python -m twine upload --repository testpypi dist/*
- Test installation
  - > python -m pip install --index-url https://test.pypi.org/simple/ pybenutils -U
- Deploy to repo (pypi)
  - > python -m twine upload --repository pypi dist/*

### Installation
> python -m pip install pybenutils -U