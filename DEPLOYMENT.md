### Deployment check list
- Install deployment requirements
  ```bash
  python -m pip install -r deploy_requirements.txt -U
  ```

- Test the package
  ```bash
  pytest .
  ```

- Build the package
  ```bash
  python -m build
  ```

- README.md description test
  ```bash
  twine check dist/*
  ```

- Deploy to repo (testpypi)
  ```bash
  python -m twine upload --repository testpypi dist/*
  ```

- Test installation
  ```bash
  python -m pip install --index-url https://test.pypi.org/simple/ pybenutils -U
  ```

- Deploy to repo (pypi)
  ```bash
  python -m twine upload --repository pypi dist/*
  ```
