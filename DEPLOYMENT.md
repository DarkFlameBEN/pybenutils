### Deployment check list
- Install deployment requirements
  > python -m pip install -r deploy_requirements.txt -U
- Test the package
  > pytest .
- Build the package
  > python -m build
- README.md description test
  > twine check dist/*
- Deploy to repo (testpypi)
  > python -m twine upload --repository testpypi dist/*
- Test installation
  > python -m pip install --index-url https://test.pypi.org/simple/ pybenutils -U
- Deploy to repo (pypi)
  > python -m twine upload --repository pypi dist/*
