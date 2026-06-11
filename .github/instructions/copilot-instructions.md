---
description: Instructions to force AI to use virtual environments for Python projects, ensuring that dependencies are managed correctly and do not interfere with the global Python installation.
applyTo: '**'
---
To ensure that AI uses virtual environments for Python projects, follow these instructions:
1. **Create a Virtual Environment**: Use the following command to create a virtual environment in your project directory:
   ```bash
   python -m venv .venv
   ```
2. **Activate the Virtual Environment**:
   - On Windows:
     ```bash
     .\.venv\Scripts\Activate.ps1
     ```
   - On macOS and Linux:
     ```bash
     source .venv/bin/activate
     ```
3. **Install Dependencies**: Use pip to install any necessary dependencies within the virtual environment:
   ```bash
    pip install -e .
    ```
4. **Configure AI to Use the Virtual Environment**: Ensure that your AI tool is configured to use the Python interpreter from the virtual environment. This typically involves setting the interpreter path in your AI tool's settings to point to the `.venv` directory created in step 1.
By following these steps, you can ensure that your AI uses the virtual environment for Python projects, keeping dependencies isolated and preventing conflicts with the global Python installation.